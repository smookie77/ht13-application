"""Create a demo event so the SPA has something to render locally.

Idempotent: re-running it resets the demo event's stock instead of piling up
duplicates, which is exactly what you want between load-test runs.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event, TicketType

SLUG = "hack-tues-13"


class Command(BaseCommand):
    help = "Seed a demo event with ticket types."

    def add_arguments(self, parser):
        parser.add_argument(
            "--open-now",
            action="store_true",
            help="Open sales immediately instead of in one hour.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        opens_in = timedelta(minutes=-5) if options["open_now"] else timedelta(hours=1)
        sales_open_at = now + opens_in

        event, created = Event.objects.update_or_create(
            slug=SLUG,
            defaults={
                "title": "Hack TUES 13",
                "tagline": "48 hours. One idea. Build it.",
                "description": (
                    "The thirteenth edition of the largest high-school hackathon in "
                    "Bulgaria. Two days of building, mentors from the industry, and "
                    "a demo night in front of a packed hall."
                ),
                "venue_name": "TUES @ TU-Sofia",
                "venue_address": "8 Kliment Ohridski Blvd",
                "city": "Sofia",
                "starts_at": now + timedelta(days=30),
                "ends_at": now + timedelta(days=32),
                "doors_open_at": now + timedelta(days=30, hours=-1),
                "sales_open_at": sales_open_at,
                "sales_close_at": now + timedelta(days=29),
                "is_published": True,
                "has_seating": False,
            },
        )

        tiers = [
            ("Standing", "General admission, standing area.", 2000, 300, 4, 0),
            ("Standard", "Seated in the main hall.", 4500, 150, 4, 1),
            ("VIP", "Front rows, backstage tour, merch pack.", 9000, 50, 2, 2),
        ]
        for name, description, price_minor, quantity, max_per_order, sort_order in tiers:
            TicketType.objects.update_or_create(
                event=event,
                name=name,
                defaults={
                    "description": description,
                    "price_minor": price_minor,
                    "currency": "BGN",
                    "quantity_total": quantity,
                    "quantity_available": quantity,
                    "max_per_order": max_per_order,
                    "sort_order": sort_order,
                    "is_active": True,
                },
            )

        verb = "Created" if created else "Reset"
        self.stdout.write(self.style.SUCCESS(f"{verb} demo event '{event.title}' ({SLUG})."))
