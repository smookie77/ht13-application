from rest_framework import serializers

from . import queue
from .models import Reservation


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
