import pytest
from rest_framework.test import APIClient

from apps.integrations.storage import get_ticket_storage
from apps.ticketing import issuing, services
from apps.ticketing.models import Reservation, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def confirmed(verified_user, ticket_type, event):
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=2
    )
    services.allocate(reservation)
    reservation.refresh_from_db()
    return services.confirm_reservation(reservation)


def test_one_ticket_per_admission(confirmed):
    tickets = issuing.create_tickets(confirmed)
    assert len(tickets) == confirmed.quantity


def test_minting_tickets_is_idempotent(confirmed):
    """A retried task must not hand the same buyer a second set of tickets."""
    first = issuing.create_tickets(confirmed)
    second = issuing.create_tickets(confirmed)

    assert {t.code for t in first} == {t.code for t in second}
    assert Ticket.objects.filter(reservation=confirmed).count() == confirmed.quantity


def test_unconfirmed_reservation_cannot_be_ticketed(verified_user, ticket_type, event):
    reservation = Reservation.objects.create(
        user=verified_user, event=event, ticket_type=ticket_type, quantity=1
    )
    with pytest.raises(ValueError):
        issuing.create_tickets(reservation)


def test_ticket_codes_are_unique(confirmed):
    codes = {issuing.create_tickets(confirmed)[0].code for _ in range(1)}
    more = {Ticket.objects.create(reservation=confirmed, holder_name="X").code
            for _ in range(50)}
    assert len(more | codes) == 51


def test_pdf_is_rendered_and_stored(confirmed):
    ticket = issuing.create_tickets(confirmed)[0]
    pdf = issuing.build_pdf(ticket)

    assert pdf.startswith(b"%PDF-")
    key = issuing.store_pdf(ticket, pdf)

    ticket.refresh_from_db()
    assert ticket.pdf_key == key
    assert get_ticket_storage().read(key) == pdf


def test_holder_name_is_frozen_at_issue_time(confirmed, verified_user):
    """The PDF is a historical document - renaming the account later must not
    change a ticket that is already in someone's inbox."""
    ticket = issuing.create_tickets(confirmed)[0]
    original = ticket.holder_name

    verified_user.full_name = "Someone Else"
    verified_user.save(update_fields=["full_name"])

    ticket.refresh_from_db()
    assert ticket.holder_name == original


def test_issue_tickets_sends_one_email_with_attachments(confirmed, settings):
    settings.EMAIL_SENDER_CLASS = "apps.integrations.email.console.ConsoleEmailSender"
    tickets = issuing.issue_tickets(confirmed)

    assert len(tickets) == 2
    for ticket in tickets:
        ticket.refresh_from_db()
        assert ticket.emailed_at is not None
        assert ticket.pdf_key


def test_download_requires_ownership(api, confirmed, unverified_user):
    ticket = issuing.create_tickets(confirmed)[0]
    issuing.store_pdf(ticket, issuing.build_pdf(ticket))

    api.force_authenticate(unverified_user)
    assert api.get(f"/api/tickets/{ticket.code}/download/").status_code == 404


def test_owner_can_download_pdf(api, confirmed, verified_user):
    ticket = issuing.create_tickets(confirmed)[0]
    issuing.store_pdf(ticket, issuing.build_pdf(ticket))

    api.force_authenticate(verified_user)
    response = api.get(f"/api/tickets/{ticket.code}/download/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_download_rebuilds_a_missing_pdf(api, confirmed, verified_user):
    """Storage losing an object must not leave a paying customer stuck."""
    ticket = issuing.create_tickets(confirmed)[0]

    api.force_authenticate(verified_user)
    response = api.get(f"/api/tickets/{ticket.code}/download/")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_check_in_requires_staff(api, confirmed, verified_user):
    ticket = issuing.create_tickets(confirmed)[0]
    api.force_authenticate(verified_user)
    response = api.post("/api/tickets/check-in/", {"code": ticket.code}, format="json")
    assert response.status_code == 403


def test_staff_can_check_in_once(api, confirmed, django_user_model):
    ticket = issuing.create_tickets(confirmed)[0]
    staff = django_user_model.objects.create_user(
        email="steward@example.com", full_name="Door Staff", password="s3cure-passphrase!"
    )
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    api.force_authenticate(staff)

    first = api.post("/api/tickets/check-in/", {"code": ticket.code}, format="json")
    assert first.status_code == 200
    assert first.data["is_checked_in"] is True

    # A second scan is a conflict, not a silent success.
    second = api.post("/api/tickets/check-in/", {"code": ticket.code}, format="json")
    assert second.status_code == 409


def test_check_in_rejects_unknown_code(api, django_user_model):
    staff = django_user_model.objects.create_user(
        email="steward2@example.com", full_name="Door Staff", password="s3cure-passphrase!"
    )
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    api.force_authenticate(staff)

    response = api.post("/api/tickets/check-in/", {"code": "NOPE-NOPE"}, format="json")
    assert response.status_code == 404


def test_qr_encodes_the_check_in_url(confirmed):
    ticket = issuing.create_tickets(confirmed)[0]
    assert issuing.check_in_url(ticket.code).endswith(f"/check-in/{ticket.code}")
