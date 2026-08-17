from rest_framework import serializers

from . import queue
from .models import Reservation, Ticket


class CreateReservationSerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=10, default=1)


class ReservationSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    event_slug = serializers.CharField(source="event.slug", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    position = serializers.SerializerMethodField()
    seconds_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "public_id",
            "event_slug",
            "event_title",
            "ticket_type_name",
            "quantity",
            "status",
            "failure_reason",
            "sequence",
            "position",
            "seconds_left",
            "created_at",
            "allocated_at",
            "expires_at",
            "confirmed_at",
        ]
        read_only_fields = fields

    def get_position(self, obj) -> int | None:
        """People still ahead in line. None once the queue no longer matters."""
        if obj.status != "queued":
            return None
        return queue.position_for(obj.sequence, event_id=obj.event_id)


class TicketSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="reservation.event.title", read_only=True)
    event_slug = serializers.CharField(source="reservation.event.slug", read_only=True)
    starts_at = serializers.DateTimeField(source="reservation.event.starts_at", read_only=True)
    venue_name = serializers.CharField(source="reservation.event.venue_name", read_only=True)
    ticket_type_name = serializers.CharField(
        source="reservation.ticket_type.name", read_only=True
    )
    is_checked_in = serializers.BooleanField(read_only=True)
    # The storage key is deliberately absent: downloads go through the
    # authenticated endpoint, never a raw bucket path.
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "code",
            "holder_name",
            "event_title",
            "event_slug",
            "ticket_type_name",
            "starts_at",
            "venue_name",
            "issued_at",
            "emailed_at",
            "is_checked_in",
            "checked_in_at",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        return f"/api/tickets/{obj.code}/download/"


class CheckInSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
