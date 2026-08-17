from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import IsEmailVerified

from . import services
from .models import Reservation
from .serializers import CreateReservationSerializer, ReservationSerializer

PUBLIC_ID_PARAM = OpenApiParameter("public_id", OpenApiTypes.UUID, OpenApiParameter.PATH)


@extend_schema_view(
    # The lookup is a UUID, not the numeric pk - spelling that out keeps the
    # generated client honest.
    retrieve=extend_schema(
        parameters=[PUBLIC_ID_PARAM]
    )
)
class ReservationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Buying tickets.

    Authorisation is ownership-based throughout: the queryset is filtered to
    the requesting user, so there is no object id a buyer can guess their way
    into someone else's order with.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReservationSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user).select_related(
            "event", "ticket_type"
        )

    def get_permissions(self):
        # Only the act of taking a ticket needs a confirmed address; reading
        # your own history does not.
        if self.action == "create":
            return [IsAuthenticated(), IsEmailVerified()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "reservation-create"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        request=CreateReservationSerializer, responses={202: ReservationSerializer}
    )
    def create(self, request):
        """Join the queue. Returns immediately - allocation happens out of band.

        202 rather than 201 is the honest status code: the request has been
        accepted into the line, but nobody has a ticket yet.
        """
        serializer = CreateReservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reservation = services.request_reservation(
            user=request.user, **serializer.validated_data
        )
        return Response(
            ReservationSerializer(reservation).data, status=status.HTTP_202_ACCEPTED
        )

    @extend_schema(
        request=None,
        responses={200: ReservationSerializer},
        parameters=[PUBLIC_ID_PARAM],
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, public_id=None):
        """Simulated payment step - where Stripe would go."""
        reservation = services.confirm_reservation(self.get_object())
        self._broadcast(reservation)
        return Response(ReservationSerializer(reservation).data)

    @extend_schema(
        request=None,
        responses={200: ReservationSerializer},
        parameters=[PUBLIC_ID_PARAM],
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, public_id=None):
        reservation = services.cancel_reservation(self.get_object())
        self._broadcast(reservation)
        return Response(ReservationSerializer(reservation).data)

    def _broadcast(self, reservation):
        from . import realtime

        realtime.broadcast_availability(services._reload_event(reservation.event_id))
