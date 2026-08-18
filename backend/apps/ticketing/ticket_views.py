"""Ticket delivery and door check-in."""

import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from . import issuing
from .models import Ticket
from .serializers import CheckInSerializer, TicketSerializer

logger = logging.getLogger(__name__)


CODE_PARAM = OpenApiParameter("code", OpenApiTypes.STR, OpenApiParameter.PATH)


@extend_schema_view(retrieve=extend_schema(parameters=[CODE_PARAM]))
class TicketViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """A buyer's issued tickets.

    Scoped to the requesting user's own reservations, so a ticket code from
    someone else's order simply does not resolve.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer
    lookup_field = "code"

    def get_queryset(self):
        return Ticket.objects.filter(
            reservation__user=self.request.user
        ).select_related("reservation", "reservation__event", "reservation__ticket_type")

    @extend_schema(
        parameters=[CODE_PARAM],
        responses={
            200: OpenApiResponse(description="PDF stream (local storage)"),
            302: OpenApiResponse(description="Redirect to a short-lived signed URL"),
        },
    )
    @action(detail=True, methods=["get"])
    def download(self, request, code=None):
        """Download the PDF.

        Authorisation happens here rather than by handing out a bare storage
        URL: the bucket stays private, and the signed URL that may be issued
        below lives for minutes, not forever.
        """
        ticket = self.get_object()
        url, pdf = issuing.download_target(ticket)

        if url:
            return HttpResponseRedirect(url)

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{ticket.code}.pdf"'
        return response


@extend_schema(
    request=CheckInSerializer,
    responses={200: TicketSerializer, 404: OpenApiResponse(description="Unknown code")},
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def check_in(request):
    """Admit a ticket at the door. Staff only.

    Deliberately reports an already-used ticket as a conflict rather than
    silently succeeding - a duplicate scan is exactly what a steward needs to
    be told about.
    """
    serializer = CheckInSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        ticket = Ticket.objects.select_related(
            "reservation", "reservation__event"
        ).get(code=serializer.validated_data["code"].strip().upper())
    except Ticket.DoesNotExist:
        return Response(
            {"detail": "Unknown ticket code."}, status=status.HTTP_404_NOT_FOUND
        )

    if ticket.is_checked_in:
        return Response(
            {
                "detail": "This ticket has already been used.",
                "ticket": TicketSerializer(ticket).data,
            },
            status=status.HTTP_409_CONFLICT,
        )

    ticket.checked_in_at = timezone.now()
    ticket.checked_in_by = request.user
    ticket.save(update_fields=["checked_in_at", "checked_in_by"])

    return Response(TicketSerializer(ticket).data)
