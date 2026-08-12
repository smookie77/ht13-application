from django.urls import path

from .consumers import AvailabilityConsumer, ReservationConsumer

websocket_urlpatterns = [
    path("ws/events/<slug:slug>/", AvailabilityConsumer.as_asgi()),
    path("ws/reservations/<str:public_id>/", ReservationConsumer.as_asgi()),
]
