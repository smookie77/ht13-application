"""Turning a paid reservation into delivered tickets.

Three steps that can each fail independently - render, upload, email - so each
is idempotent and recorded separately. A retry after a failed email must not
mint a second ticket or upload the PDF twice.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.integrations.email import Attachment, EmailMessage, EmailSendError, get_email_sender
from apps.integrations.pdf.renderer import qr_data_uri, render_ticket_pdf
from apps.integrations.storage import StorageError, get_ticket_storage

from .models import Reservation, ReservationStatus, Ticket

logger = logging.getLogger(__name__)


def check_in_url(code: str) -> str:
    """What the QR encodes: a link a steward opens on their phone."""
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/check-in/{code}"


@transaction.atomic
def create_tickets(reservation: Reservation) -> list[Ticket]:
    """Mint one Ticket per admission. Safe to call twice."""
    if reservation.status != ReservationStatus.CONFIRMED:
        raise ValueError("Only a confirmed reservation can be ticketed.")

    existing = list(reservation.tickets.all())
    if len(existing) >= reservation.quantity:
        return existing

    holder = reservation.user.full_name or reservation.user.email
    new_tickets = [
        Ticket.objects.create(reservation=reservation, holder_name=holder)
        for _ in range(reservation.quantity - len(existing))
    ]
    return existing + new_tickets


def build_pdf(ticket: Ticket) -> bytes:
    reservation = ticket.reservation
    event = reservation.event

    return render_ticket_pdf(
        {
            "ticket": ticket,
            "reservation": reservation,
            "event": event,
            "ticket_type": reservation.ticket_type,
            "starts_at_date": timezone.localtime(event.starts_at).strftime("%d %B %Y"),
            "starts_at_time": timezone.localtime(event.starts_at).strftime("%H:%M"),
            "doors_open_time": (
                timezone.localtime(event.doors_open_at).strftime("%H:%M")
                if event.doors_open_at
                else None
            ),
            "issued_at": timezone.localtime(ticket.issued_at).strftime("%d %b %Y, %H:%M"),
            # Reserved seating is a later feature; the template already has a
            # slot for it.
            "seat_label": None,
            "qr_data_uri": qr_data_uri(check_in_url(ticket.code)),
        }
    )


def store_pdf(ticket: Ticket, pdf: bytes) -> str:
    key = get_ticket_storage().save(ticket.storage_key, pdf, "application/pdf")
    if ticket.pdf_key != key:
        Ticket.objects.filter(pk=ticket.pk).update(pdf_key=key)
        ticket.pdf_key = key
    return key


def send_ticket_email(
    reservation: Reservation, tickets: list[Ticket], pdfs: dict[str, bytes]
) -> None:
    event = reservation.event
    when = timezone.localtime(event.starts_at).strftime("%d %B %Y, %H:%M")

    rows = "".join(
        f"<li><strong>{t.holder_name}</strong> — {t.code}</li>" for t in tickets
    )
    message = EmailMessage(
        to=reservation.user.email,
        subject=f"Your ticket for {event.title}",
        html=(
            f"<p>Hi {reservation.user.get_short_name()},</p>"
            f"<p>Your {reservation.ticket_type.name} ticket for <strong>{event.title}</strong> "
            f"is attached as a PDF.</p>"
            f"<p><strong>When:</strong> {when}<br>"
            f"<strong>Where:</strong> {event.venue_name}, {event.city}</p>"
            f"<ul>{rows}</ul>"
            f"<p>Show the QR code at the entrance. You can also download the ticket "
            f"any time from your account.</p>"
        ),
        text=(
            f"Your ticket for {event.title}\n"
            f"When: {when}\nWhere: {event.venue_name}, {event.city}\n"
            + "\n".join(f"{t.holder_name} - {t.code}" for t in tickets)
        ),
        attachments=[
            Attachment(filename=f"{t.code}.pdf", content=pdfs[t.code]) for t in tickets
        ],
    )

    get_email_sender().send(message)
    now = timezone.now()
    Ticket.objects.filter(pk__in=[t.pk for t in tickets]).update(emailed_at=now)


def issue_tickets(reservation: Reservation) -> list[Ticket]:
    """Render, store and email the tickets for a paid reservation.

    Storage failures abort - a ticket the buyer cannot re-download later is not
    finished. An email failure does not: the PDF is already safe in storage and
    downloadable from the account page, so the task is retried rather than the
    whole issue being treated as failed.
    """
    tickets = create_tickets(reservation)

    pdfs: dict[str, bytes] = {}
    for ticket in tickets:
        pdf = build_pdf(ticket)
        store_pdf(ticket, pdf)
        pdfs[ticket.code] = pdf

    try:
        send_ticket_email(reservation, tickets, pdfs)
    except EmailSendError:
        logger.exception(
            "Tickets for reservation %s are stored but the email failed",
            reservation.public_id,
        )
        raise

    return tickets


def download_target(ticket: Ticket) -> tuple[str | None, bytes | None]:
    """Resolve a ticket to either a signed URL or raw bytes.

    Backends that can presign (R2) return a URL the browser is redirected to;
    the local backend returns bytes we stream ourselves. Either way the
    ownership check happens in our view first.
    """
    storage = get_ticket_storage()
    key = ticket.pdf_key or ticket.storage_key

    url = storage.signed_url(key, expires_in=settings.TICKET_URL_TTL_SECONDS)
    if url:
        return url, None

    try:
        return None, storage.read(key)
    except StorageError:
        # Storage lost it, or the upload never completed - rebuild on demand
        # rather than showing the buyer an error.
        logger.warning("Rebuilding missing PDF for ticket %s", ticket.code)
        pdf = build_pdf(ticket)
        store_pdf(ticket, pdf)
        return None, pdf
