import logging

from celery import shared_task

from . import issuing, services
from .models import Reservation

logger = logging.getLogger(__name__)


@shared_task(name="ticketing.expire_stale_holds")
def expire_stale_holds():
    """Return abandoned holds to the pool. Scheduled by Celery beat."""
    count = services.expire_stale_holds()
    if count:
        logger.info("Expired %s stale reservation hold(s)", count)
    return count


@shared_task(
    name="ticketing.issue_tickets",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def issue_tickets(self, reservation_public_id: str):
    """Render, store and email the tickets for a paid reservation.

    Off the request path because it is slow and involves two third parties.
    Retried with backoff, and every step is idempotent, so a retry after a
    failed email does not mint a second ticket.
    """
    try:
        reservation = Reservation.objects.select_related(
            "user", "event", "ticket_type"
        ).get(public_id=reservation_public_id)
    except Reservation.DoesNotExist:
        logger.warning("No reservation %s to issue tickets for", reservation_public_id)
        return 0

    tickets = issuing.issue_tickets(reservation)
    logger.info(
        "Issued %s ticket(s) for reservation %s", len(tickets), reservation_public_id
    )
    return len(tickets)
