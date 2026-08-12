from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "event",
        "ticket_type",
        "quantity",
        "status",
        "sequence",
        "created_at",
    )
    list_filter = ("status", "event", "ticket_type")
    search_fields = ("public_id", "user__email", "user__full_name")
    readonly_fields = ("public_id", "sequence", "created_at", "allocated_at", "confirmed_at")
    date_hierarchy = "created_at"
