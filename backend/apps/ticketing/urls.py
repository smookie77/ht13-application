from django.urls import path
from rest_framework.routers import DefaultRouter

from .ticket_views import TicketViewSet, check_in
from .views import ReservationViewSet

router = DefaultRouter()
router.register("reservations", ReservationViewSet, basename="reservation")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("tickets/check-in/", check_in, name="ticket-check-in"),
    *router.urls,
]
