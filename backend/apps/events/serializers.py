from rest_framework import serializers

from .models import Event, TicketType


class TicketTypeSerializer(serializers.ModelSerializer):
    price = serializers.FloatField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketType
        fields = [
            "id",
            "name",
            "description",
            "price",
            "price_minor",
            "currency",
            "quantity_total",
            "quantity_available",
            "max_per_order",
            "is_sold_out",
        ]


class EventListSerializer(serializers.ModelSerializer):
    sales_state = serializers.CharField(read_only=True)
    tickets_available = serializers.IntegerField(read_only=True)
    tickets_total = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "slug",
            "title",
            "tagline",
            "city",
            "venue_name",
            "starts_at",
            "hero_image_url",
            "sales_state",
            "tickets_available",
            "tickets_total",
        ]


class EventDetailSerializer(EventListSerializer):
    ticket_types = TicketTypeSerializer(many=True, read_only=True)

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + [
            "description",
            "venue_address",
            "ends_at",
            "doors_open_at",
            "sales_open_at",
            "sales_close_at",
            "has_seating",
            "ticket_types",
        ]


class AvailabilitySerializer(serializers.Serializer):
    """Shape of the availability payload, served over both HTTP and WebSocket."""

    slug = serializers.CharField()
    sales_state = serializers.CharField()
    tickets_available = serializers.IntegerField()
    tickets_total = serializers.IntegerField()
    ticket_types = serializers.ListField(child=serializers.DictField())
