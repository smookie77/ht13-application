"""The single consumer that makes ticket handout fair.

Run exactly one of these per event. Because there is only one popper, buyers
are served in the precise order Redis received them - no locking, no lottery.
Running two by accident is survivable but not fair: the conditional UPDATE in
`allocate()` still prevents overselling, you just lose strict ordering.
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.events.models import Event
from apps.ticketing import queue, realtime, services
from apps.ticketing.models import Reservation, ReservationStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Serve the ticket queue for an event, strictly first-come first-served."

    def add_arguments(self, parser):
        parser.add_argument("--event", required=True, help="Event slug to serve.")
        parser.add_argument(
            "--broadcast-every",
            type=float,
            default=0.25,
            help="Seconds to coalesce stock broadcasts (0 sends one per allocation).",
        )

    def handle(self, *args, **options):
        event = Event.objects.get(slug=options["event"])
        interval = options["broadcast_every"]

        self._running = True
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._stop)

        self.stdout.write(
            self.style.SUCCESS(f"Allocator serving '{event.slug}'. Ctrl-C to stop.")
        )

        last_broadcast = 0.0
        pending_broadcast = False

        while self._running:
            public_id = queue.pop_blocking(event.id, timeout=2)

            if public_id is None:
                # Idle tick: flush any broadcast the coalescing window held back.
                if pending_broadcast:
                    self._broadcast(event)
                    last_broadcast, pending_broadcast = time.monotonic(), False
                close_old_connections()
                continue

            try:
                self._serve(public_id, event)
            except Exception:
                logger.exception("Failed to allocate reservation %s", public_id)
            finally:
                queue.mark_served(event.id)

            pending_broadcast = True
            now = time.monotonic()
            if now - last_broadcast >= interval:
                self._broadcast(event)
                last_broadcast, pending_broadcast = now, False

        self.stdout.write(self.style.WARNING("Allocator stopped."))

    def _serve(self, public_id: str, event: Event) -> None:
        try:
            reservation = Reservation.objects.select_related("ticket_type").get(
                public_id=public_id
            )
        except Reservation.DoesNotExist:
            logger.warning("Queued id %s has no reservation row", public_id)
            return

        if reservation.status != ReservationStatus.QUEUED:
            return  # cancelled while waiting, or a duplicate delivery

        services.allocate(reservation)
        realtime.notify_reservation(reservation)

    def _broadcast(self, event: Event) -> None:
        realtime.broadcast_availability(services._reload_event(event.id))

    def _stop(self, *_args):
        self._running = False
