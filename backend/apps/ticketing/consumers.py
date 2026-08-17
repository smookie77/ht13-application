"""WebSocket endpoints.

Both consumers are read-only: the browser never sends commands over the
socket, it only listens. Buying still goes through the authenticated HTTP API,
which keeps the trust boundary in one place.
"""

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.events.models import Event
from apps.events.selectors import availability_payload

from . import queue
from .models import Reservation
from .realtime import event_group, reservation_group

logger = logging.getLogger(__name__)


class HeartbeatMixin:
    """Answer client pings.

    Reverse proxies - Cloudflare among them - drop WebSockets that go quiet for
    a couple of minutes, and a queue can easily be idle that long between
    allocations. The client pings periodically; this keeps the connection
    counted as active. Anything else the client sends is ignored: these sockets
    are read-only, and every state change goes through the authenticated HTTP
    API.
    """

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})


class AvailabilityConsumer(HeartbeatMixin, AsyncJsonWebsocketConsumer):
    """Live ticket counts for one event. Public - no login needed."""

    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]

        snapshot = await self._snapshot(self.slug)
        if snapshot is None:
            await self.close(code=4404)
            return

        await self.channel_layer.group_add(event_group(self.slug), self.channel_name)
        await self.accept()
        # Send the current state immediately so a client that connects between
        # two allocations is not left staring at a stale number.
        await self.send_json({"type": "availability.update", "payload": snapshot})

    async def disconnect(self, code):
        if hasattr(self, "slug"):
            await self.channel_layer.group_discard(
                event_group(self.slug), self.channel_name
            )

    async def availability_update(self, message):
        await self.send_json({"type": "availability.update", "payload": message["payload"]})

    @database_sync_to_async
    def _snapshot(self, slug):
        try:
            event = Event.objects.prefetch_related("ticket_types").get(
                slug=slug, is_published=True
            )
        except Event.DoesNotExist:
            return None
        payload = availability_payload(event)
        payload["now_serving"] = queue.get_served(event.id)
        payload["queue_length"] = queue.queue_length(event.id)
        return payload


class ReservationConsumer(HeartbeatMixin, AsyncJsonWebsocketConsumer):
    """Live status of one reservation: queue position, then the verdict.

    Authorisation matters here - this stream reveals order state, so the socket
    is only accepted for the reservation's own owner.
    """

    async def connect(self):
        self.public_id = self.scope["url_route"]["kwargs"]["public_id"]
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        snapshot = await self._snapshot(self.public_id, user)
        if snapshot is None:
            await self.close(code=4404)
            return

        await self.channel_layer.group_add(
            reservation_group(self.public_id), self.channel_name
        )
        await self.accept()
        await self.send_json({"type": "reservation.update", "payload": snapshot})

    async def disconnect(self, code):
        if hasattr(self, "public_id"):
            await self.channel_layer.group_discard(
                reservation_group(self.public_id), self.channel_name
            )

    async def reservation_update(self, message):
        await self.send_json({"type": "reservation.update", "payload": message["payload"]})

    @database_sync_to_async
    def _snapshot(self, public_id, user):
        try:
            # Filtering by user is the authorisation check: another person's
            # id simply does not resolve.
            reservation = Reservation.objects.get(public_id=public_id, user=user)
        except (Reservation.DoesNotExist, ValueError, TypeError):
            return None
        return {
            "public_id": str(reservation.public_id),
            "status": reservation.status,
            "sequence": reservation.sequence,
            "position": queue.position_for(
                reservation.sequence, event_id=reservation.event_id
            ),
            "failure_reason": reservation.failure_reason,
            "seconds_left": reservation.seconds_left,
        }
