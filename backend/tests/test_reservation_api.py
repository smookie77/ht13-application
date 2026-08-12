import pytest
from rest_framework.test import APIClient

from apps.events.models import TicketType
from apps.ticketing import queue, services
from apps.ticketing.models import Reservation, ReservationStatus

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def api():
    return APIClient()


def test_unverified_user_cannot_reserve(api, unverified_user, ticket_type):
    api.force_authenticate(unverified_user)
    response = api.post(
        "/api/reservations/", {"ticket_type_id": ticket_type.pk}, format="json"
    )
    assert response.status_code == 403


def test_anonymous_cannot_reserve(api, ticket_type):
    response = api.post(
        "/api/reservations/", {"ticket_type_id": ticket_type.pk}, format="json"
    )
    assert response.status_code == 403


def test_reserve_returns_202_and_joins_queue(api, verified_user, ticket_type, event):
    queue.reset_queue(event.id)
    api.force_authenticate(verified_user)

    response = api.post(
        "/api/reservations/", {"ticket_type_id": ticket_type.pk, "quantity": 2}, format="json"
    )

    assert response.status_code == 202
    assert response.data["status"] == ReservationStatus.QUEUED
    # Nothing is deducted until the allocator gets to it.
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 10
    assert queue.queue_length(event.id) == 1


def test_quantity_above_tier_limit_is_rejected(api, verified_user, ticket_type):
    api.force_authenticate(verified_user)
    response = api.post(
        "/api/reservations/",
        {"ticket_type_id": ticket_type.pk, "quantity": ticket_type.max_per_order + 1},
        format="json",
    )
    assert response.status_code == 400


def test_one_open_request_per_user(api, verified_user, ticket_type, event):
    queue.reset_queue(event.id)
    api.force_authenticate(verified_user)
    payload = {"ticket_type_id": ticket_type.pk}

    assert api.post("/api/reservations/", payload, format="json").status_code == 202
    second = api.post("/api/reservations/", payload, format="json")
    assert second.status_code == 400


def test_user_cannot_read_another_users_reservation(
    api, verified_user, unverified_user, ticket_type, event
):
    other = Reservation.objects.create(
        user=unverified_user, event=event, ticket_type=ticket_type, quantity=1
    )
    api.force_authenticate(verified_user)

    response = api.get(f"/api/reservations/{other.public_id}/")
    assert response.status_code == 404


def test_confirm_marks_reservation_paid(api, verified_user, ticket_type, event):
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=1
    )
    services.allocate(reservation)

    api.force_authenticate(verified_user)
    response = api.post(f"/api/reservations/{reservation.public_id}/confirm/")

    assert response.status_code == 200
    assert response.data["status"] == ReservationStatus.CONFIRMED
    # Stock stays deducted - a confirmed ticket keeps its seat.
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 9


def test_queued_reservation_cannot_be_confirmed(api, verified_user, ticket_type, event):
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=1
    )
    api.force_authenticate(verified_user)

    response = api.post(f"/api/reservations/{reservation.public_id}/confirm/")
    assert response.status_code == 400


def test_sold_out_reservation_is_rejected_not_oversold(
    api, verified_user, ticket_type, event
):
    TicketType.objects.filter(pk=ticket_type.pk).update(quantity_available=0)
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=1
    )

    services.allocate(reservation)
    reservation.refresh_from_db()

    assert reservation.status == ReservationStatus.REJECTED
    assert TicketType.objects.get(pk=ticket_type.pk).quantity_available == 0
