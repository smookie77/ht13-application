from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """A single sellable event (concert, match, hackathon...)."""

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    tagline = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)

    venue_name = models.CharField(max_length=200)
    venue_address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    doors_open_at = models.DateTimeField(null=True, blank=True)

    sales_open_at = models.DateTimeField()
    sales_close_at = models.DateTimeField()

    hero_image_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=False)

    # Reserved seating is a bonus feature; the flag lets the ordering flow
    # branch on it once a Seat model lands, without another schema change.
    has_seating = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["is_published", "starts_at"])]

    def __str__(self):
        return self.title

    @property
    def sales_state(self) -> str:
        now = timezone.now()
        if now < self.sales_open_at:
            return "upcoming"
        if now > self.sales_close_at:
            return "closed"
        return "open" if self.tickets_available > 0 else "sold_out"

    @property
    def tickets_available(self) -> int:
        return sum(tt.quantity_available for tt in self.ticket_types.all())

    @property
    def tickets_total(self) -> int:
        return sum(tt.quantity_total for tt in self.ticket_types.all())


class TicketType(models.Model):
    """A price tier within an event (standing, standard, VIP...).

    `quantity_available` is the authoritative stock counter. It is only ever
    mutated through a conditional UPDATE (`WHERE quantity_available > 0`),
    which makes overselling impossible at the database level regardless of
    how many workers run concurrently. The CheckConstraint is the last line
    of defence: any code path that would drive it negative fails loudly.
    """

    event = models.ForeignKey(Event, related_name="ticket_types", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)

    # Money is stored in minor units (stotinki) to avoid float rounding.
    price_minor = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="BGN")

    quantity_total = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    quantity_available = models.PositiveIntegerField()
    max_per_order = models.PositiveSmallIntegerField(default=4)

    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "price_minor"]
        constraints = [
            models.UniqueConstraint(fields=["event", "name"], name="uniq_ticket_type_per_event"),
            models.CheckConstraint(
                condition=models.Q(quantity_available__lte=models.F("quantity_total")),
                name="available_not_above_total",
            ),
        ]

    def __str__(self):
        return f"{self.event.title} - {self.name}"

    @property
    def price(self) -> float:
        return self.price_minor / 100

    @property
    def is_sold_out(self) -> bool:
        return self.quantity_available == 0
