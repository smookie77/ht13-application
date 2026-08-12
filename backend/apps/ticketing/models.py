import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReservationStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    ALLOCATED = "allocated", "Allocated"  # stock held, awaiting payment
    CONFIRMED = "confirmed", "Confirmed"  # paid, ticket issued
    REJECTED = "rejected", "Rejected"  # sold out before their turn
    EXPIRED = "expired", "Expired"  # hold ran out
    CANCELLED = "cancelled", "Cancelled"  # user backed out


class Reservation(models.Model):
    """One person's request for tickets, and its journey through the queue.

    The row is written *before* any stock is touched: the HTTP request only
    records the ask and pushes an id onto Redis, which is what keeps the web
    tier fast when hundreds of people click at the same second. The allocator
    then decides, strictly in arrival order.
    """

    # Public identifier. A UUID rather than a sequential pk so one buyer cannot
    # probe other people's orders by counting.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="reservations", on_delete=models.CASCADE
    )
    event = models.ForeignKey(
        "events.Event", related_name="reservations", on_delete=models.CASCADE
    )
    ticket_type = models.ForeignKey(
        "events.TicketType", related_name="reservations", on_delete=models.CASCADE
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=20, choices=ReservationStatus.choices, default=ReservationStatus.QUEUED
    )
    failure_reason = models.CharField(max_length=200, blank=True)

    # Deli-counter ticket number, handed out by an atomic Redis INCR at enqueue
    # time. Queue position is `sequence - served`, so a client can compute its
    # own place from one broadcast counter instead of a per-user message.
    sequence = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    allocated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["event", "status"]),
        ]

    def __str__(self):
        return f"{self.public_id} ({self.status})"

    @property
    def is_active_hold(self) -> bool:
        """Holding stock right now - either awaiting payment or already paid."""
        return self.status in {ReservationStatus.ALLOCATED, ReservationStatus.CONFIRMED}

    @property
    def is_expired(self) -> bool:
        return (
            self.status == ReservationStatus.ALLOCATED
            and self.expires_at is not None
            and self.expires_at <= timezone.now()
        )

    @property
    def seconds_left(self) -> int | None:
        if self.status != ReservationStatus.ALLOCATED or not self.expires_at:
            return None
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))
