"""Reservation business rules.

Split into two halves on purpose:

* `request_reservation` runs inside the HTTP request. It must stay cheap - one
  INSERT and one Redis push - because this is the code path that hundreds of
  people hit in the same second.
* `allocate` runs in the allocator process. It is the only place that changes
  stock, and it does so with a conditional UPDATE.
"""

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.models import Event, TicketType

from . import queue, realtime
from .models import Reservation, ReservationStatus

logger = logging.getLogger(__name__)


class ReservationError(ValidationError):
    pass


def _hold_duration():
    from django.conf import settings

    return timezone.timedelta(seconds=settings.RESERVATION_HOLD_SECONDS)


def request_reservation(*, user, ticket_type_id: int, quantity: int) -> Reservation:
    """Record the ask and take a place in line. Does not touch stock."""
    from django.conf import settings

    try:
        ticket_type = TicketType.objects.select_related("event").get(
            pk=ticket_type_id, is_active=True
        )
    except TicketType.DoesNotExist as exc:
        raise ReservationError("That ticket type is not available.") from exc

    event = ticket_type.event
    if not event.is_published:
        raise ReservationError("That event is not on sale.")

    now = timezone.now()
    if now < event.sales_open_at:
        raise ReservationError("Sales have not opened yet.")
    if now > event.sales_close_at:
        raise ReservationError("Sales for this event have closed.")

    if quantity < 1 or quantity > ticket_type.max_per_order:
        raise ReservationError(
            f"You can request between 1 and {ticket_type.max_per_order} tickets."
        )

    # Stop one account from flooding the queue and starving real buyers. This
    # is a fairness rule, not just abuse control.
    open_requests = Reservation.objects.filter(
        user=user,
        event=event,
        status__in=[ReservationStatus.QUEUED, ReservationStatus.ALLOCATED],
    ).count()
    if open_requests >= settings.MAX_OPEN_RESERVATIONS_PER_USER:
        raise ReservationError(
            "You already have a request in progress for this event."
        )

    reservation = Reservation.objects.create(
        user=user,
        event=event,
        ticket_type=ticket_type,
        quantity=quantity,
        status=ReservationStatus.QUEUED,
    )

    # Enqueue only after the row is durably committed, otherwise the allocator
    # could pop an id that is not visible to its own transaction yet.
    def _push():
        sequence = queue.enqueue(event.id, str(reservation.public_id))
        Reservation.objects.filter(pk=reservation.pk).update(sequence=sequence)
        reservation.sequence = sequence

    transaction.on_commit(_push)
    return reservation


@transaction.atomic
def allocate(reservation: Reservation) -> Reservation:
    """Decide one reservation. Called only by the allocator, in queue order.

    The conditional UPDATE is the whole oversell guarantee: it can only match
    when enough stock is actually left, so two concurrent allocators still
    cannot drive the counter below zero. The CheckConstraint on TicketType
    backs it up if this is ever bypassed.
    """
    if reservation.status != ReservationStatus.QUEUED:
        return reservation  # already handled - re-delivery is harmless

    updated = TicketType.objects.filter(
        pk=reservation.ticket_type_id,
        quantity_available__gte=reservation.quantity,
    ).update(quantity_available=F("quantity_available") - reservation.quantity)

    now = timezone.now()
    if updated:
        reservation.status = ReservationStatus.ALLOCATED
        reservation.allocated_at = now
        reservation.expires_at = now + _hold_duration()
    else:
        reservation.status = ReservationStatus.REJECTED
        reservation.failure_reason = "Sold out before your turn."

    reservation.save(
        update_fields=["status", "allocated_at", "expires_at", "failure_reason"]
    )
    return reservation


def _release_stock(reservation: Reservation) -> None:
    TicketType.objects.filter(pk=reservation.ticket_type_id).update(
        quantity_available=F("quantity_available") + reservation.quantity
    )


def confirm_reservation(reservation: Reservation) -> Reservation:
    """Simulated payment. Real money (Stripe) would slot in right here.

    Re-reads the row under a lock so a hold that expired a moment ago cannot be
    confirmed after its stock was already handed to someone else.

    Note the transaction ends *before* the expiry error is raised: releasing
    the stock and then throwing from inside the same atomic block would roll
    the release straight back, leaving a dead hold sitting on a ticket.
    """
    expired = False

    with transaction.atomic():
        locked = Reservation.objects.select_for_update().get(pk=reservation.pk)

        if locked.status == ReservationStatus.CONFIRMED:
            return locked
        if locked.status != ReservationStatus.ALLOCATED:
            raise ReservationError("This reservation can no longer be paid for.")

        if locked.is_expired:
            locked.status = ReservationStatus.EXPIRED
            locked.save(update_fields=["status"])
            _release_stock(locked)
            expired = True
        else:
            locked.status = ReservationStatus.CONFIRMED
            locked.confirmed_at = timezone.now()
            locked.save(update_fields=["status", "confirmed_at"])

    if expired:
        raise ReservationError("Your hold expired. Please try again.")

    return locked


@transaction.atomic
def cancel_reservation(reservation: Reservation) -> Reservation:
    """Give the tickets back to the pool early."""
    locked = Reservation.objects.select_for_update().get(pk=reservation.pk)

    if locked.status == ReservationStatus.QUEUED:
        # Still in line: mark it cancelled and let the allocator skip it.
        locked.status = ReservationStatus.CANCELLED
        locked.save(update_fields=["status"])
        return locked

    if locked.status != ReservationStatus.ALLOCATED:
        raise ReservationError("This reservation cannot be cancelled.")

    locked.status = ReservationStatus.CANCELLED
    locked.save(update_fields=["status"])
    _release_stock(locked)
    return locked


def expire_stale_holds() -> int:
    """Return abandoned holds to the pool.

    Without this, a buyer who walks away mid-checkout keeps a ticket out of
    circulation forever. Run periodically by Celery beat.
    """
    now = timezone.now()
    stale = Reservation.objects.filter(
        status=ReservationStatus.ALLOCATED, expires_at__lte=now
    ).select_related("event")

    touched_events, count = {}, 0
    for reservation in stale:
        with transaction.atomic():
            locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
            if locked.status != ReservationStatus.ALLOCATED or not locked.is_expired:
                continue
            locked.status = ReservationStatus.EXPIRED
            locked.save(update_fields=["status"])
            _release_stock(locked)
            count += 1
        touched_events[reservation.event_id] = reservation.event
        realtime.notify_reservation(reservation)

    for event in touched_events.values():
        realtime.broadcast_availability(_reload_event(event.id))

    return count


def _reload_event(event_id: int) -> Event:
    return Event.objects.prefetch_related("ticket_types").get(pk=event_id)
