"""The tests that matter: fairness and the oversell guarantee.

These are the claims the whole architecture exists to support, so they are
tested against real Postgres and real Redis rather than mocks.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.models import F

from apps.events.models import TicketType
from apps.ticketing import queue, services
from apps.ticketing.models import Reservation, ReservationStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


def _make_users(count):
    return [
        User.objects.create_user(
            email=f"buyer{i}@example.com",
            full_name=f"Buyer {i}",
            password="s3cure-passphrase!",
            email_verified_at="2026-01-01T00:00:00Z",
        )
        for i in range(count)
    ]


def test_conditional_update_cannot_oversell(ticket_type):
    """The database-level guarantee, hammered concurrently.

    200 threads race for 10 tickets. Exactly 10 must win - this holds even if
    the allocator were accidentally run more than once.
    """
    ticket_type_id = ticket_type.pk

    def buy(_):
        try:
            return TicketType.objects.filter(
                pk=ticket_type_id, quantity_available__gte=1
            ).update(quantity_available=F("quantity_available") - 1)
        finally:
            # Each thread opens its own connection; leaking them exhausts
            # Postgres long before the test finishes.
            connections.close_all()

    with ThreadPoolExecutor(max_workers=50) as pool:
        wins = sum(pool.map(buy, range(200)))

    assert wins == 10
    assert TicketType.objects.get(pk=ticket_type_id).quantity_available == 0


def test_allocation_is_first_come_first_served(ticket_type, event):
    """Fairness: with fewer tickets than buyers, the earliest askers win."""
    queue.reset_queue(event.id)
    users = _make_users(15)

    reservations = []
    for user in users:
        reservation = Reservation.objects.create(
            user=user, event=event, ticket_type=ticket_type, quantity=1
        )
        reservation.sequence = queue.enqueue(event.id, str(reservation.public_id))
        reservation.save(update_fields=["sequence"])
        reservations.append(reservation)

    # Drain the line the way the allocator does: strictly in pop order.
    while (public_id := queue.pop_blocking(event.id, timeout=1)) is not None:
        services.allocate(Reservation.objects.get(public_id=public_id))
        queue.mark_served(event.id)

    for reservation in reservations:
        reservation.refresh_from_db()

    allocated = [r for r in reservations if r.status == ReservationStatus.ALLOCATED]
    rejected = [r for r in reservations if r.status == ReservationStatus.REJECTED]

    assert len(allocated) == 10
    assert len(rejected) == 5
    # The winners are exactly the first ten to ask - no one was leapfrogged.
    assert [r.sequence for r in allocated] == sorted(r.sequence for r in reservations)[:10]
    assert min(r.sequence for r in rejected) > max(r.sequence for r in allocated)


def test_queue_position_counts_people_ahead(ticket_type, event):
    queue.reset_queue(event.id)
    first, second, third = (
        queue.enqueue(event.id, f"res-{i}") for i in range(3)
    )

    assert queue.position_for(first, event_id=event.id) == 1
    assert queue.position_for(third, event_id=event.id) == 3

    queue.pop_blocking(event.id, timeout=1)
    queue.mark_served(event.id)

    # After one person is served everyone moves up by one.
    assert queue.position_for(second, event_id=event.id) == 1
    assert queue.position_for(third, event_id=event.id) == 2


def test_cancelling_a_hold_returns_stock(ticket_type, event, verified_user):
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=2
    )
    services.allocate(reservation)
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 8

    services.cancel_reservation(reservation)
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 10


def test_expired_hold_returns_stock(ticket_type, event, verified_user):
    from datetime import timedelta

    from django.utils import timezone

    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=3
    )
    services.allocate(reservation)
    Reservation.objects.filter(pk=reservation.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    assert services.expire_stale_holds() == 1
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 10
    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.EXPIRED


def test_expired_hold_cannot_be_confirmed(ticket_type, event, verified_user):
    from datetime import timedelta

    from django.utils import timezone

    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=1
    )
    services.allocate(reservation)
    Reservation.objects.filter(pk=reservation.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    reservation.refresh_from_db()

    with pytest.raises(services.ReservationError):
        services.confirm_reservation(reservation)

    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 10
