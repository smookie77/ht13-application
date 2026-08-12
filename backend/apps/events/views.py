from django.db.models import Prefetch
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Event, TicketType
from .selectors import availability_payload
from .serializers import (
    AvailabilitySerializer,
    EventDetailSerializer,
    EventListSerializer,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


class EventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Public, read-only catalogue of events.

    Purchasing lives in the `ticketing` app; this app only describes what is
    on sale, which keeps the read path cheap and cacheable.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = (
        Event.objects.filter(is_published=True)
        .prefetch_related(
            Prefetch(
                "ticket_types",
                queryset=TicketType.objects.filter(is_active=True),
            )
        )
    )

    def get_serializer_class(self):
        return EventListSerializer if self.action == "list" else EventDetailSerializer

    @action(detail=True, methods=["get"])
    def availability(self, request, slug=None):
        """Current stock. The SPA uses this for the initial render and then
        keeps it fresh over a WebSocket instead of polling."""
        event = self.get_object()
        return Response(AvailabilitySerializer(availability_payload(event)).data)
