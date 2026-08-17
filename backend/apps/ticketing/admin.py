from django.contrib import admin

from .models import Reservation, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ("code", "holder_name", "pdf_key", "issued_at", "emailed_at")
    can_delete = False


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
    inlines = [TicketInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("code", "holder_name", "event", "issued_at", "emailed_at", "checked_in_at")
    list_filter = ("reservation__event", "checked_in_at")
    search_fields = ("code", "holder_name", "reservation__user__email")
    readonly_fields = ("code", "pdf_key", "issued_at", "emailed_at")

    @admin.display(description="Event", ordering="reservation__event")
    def event(self, obj):
        return obj.reservation.event
