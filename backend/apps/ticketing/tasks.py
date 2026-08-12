import logging

from celery import shared_task

from . import services

logger = logging.getLogger(__name__)


@shared_task(name="ticketing.expire_stale_holds")
def expire_stale_holds():
    """Return abandoned holds to the pool. Scheduled by Celery beat."""
    count = services.expire_stale_holds()
    if count:
        logger.info("Expired %s stale reservation hold(s)", count)
    return count
