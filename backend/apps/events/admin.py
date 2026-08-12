from django.contrib import admin

from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = (
        "name",
        "price_minor",
        "currency",
        "quantity_total",
        "quantity_available",
        "max_per_order",
        "sort_order",
        "is_active",
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "starts_at", "is_published", "tickets_available")
    list_filter = ("is_published", "city")
    search_fields = ("title", "venue_name", "city")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "price_minor", "quantity_available", "quantity_total")
    list_filter = ("event", "is_active")
