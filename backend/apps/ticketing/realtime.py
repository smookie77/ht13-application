"""Server -> browser push.

Two channels, deliberately shaped differently:

* `event.<slug>` is a broadcast group. Everyone watching an event gets the
  stock counters and how far the queue has moved. Because a buyer's position is
  `sequence - served`, this one message updates every waiting person's position
  at once - O(1) messages per allocation instead of O(queue length).

* `reservation.<public_id>` is a group of one. Only terminal, personal news
  goes here: you got it, or it sold out before your turn.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.events.selectors import availability_payload

from . import queue

logger = logging.getLogger(__name__)


def event_group(slug: str) -> str:
    return f"event.{slug}"


def reservation_group(public_id) -> str:
    return f"reservation.{public_id}"


def _send(group: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:  # channel layer not configured (e.g. some test runs)
        return
    try:
        async_to_sync(layer.group_send)(group, payload)
    except Exception:
        # A dropped push must never fail an allocation - the ticket is already
        # safely committed, and clients reconcile over HTTP on reconnect.
        logger.exception("Realtime push to %s failed", group)


def broadcast_availability(event) -> None:
    payload = availability_payload(event)
    payload["now_serving"] = queue.get_served(event.id)
    payload["queue_length"] = queue.queue_length(event.id)
    _send(event_group(event.slug), {"type": "availability.update", "payload": payload})


def notify_reservation(reservation) -> None:
    _send(
        reservation_group(reservation.public_id),
        {
            "type": "reservation.update",
            "payload": {
                "public_id": str(reservation.public_id),
                "status": reservation.status,
                "sequence": reservation.sequence,
                "position": queue.position_for(
                    reservation.sequence, event_id=reservation.event_id
                ),
                "failure_reason": reservation.failure_reason,
                "seconds_left": reservation.seconds_left,
            },
        },
    )
