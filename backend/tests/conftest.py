from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.events.models import Event, TicketType
from apps.ticketing import queue

User = get_user_model()


@pytest.fixture
def event(db):
    now = timezone.now()
    return Event.objects.create(
        slug="test-event",
        title="Test Event",
        venue_name="Test Hall",
        city="Sofia",
        starts_at=now + timedelta(days=10),
        sales_open_at=now - timedelta(hours=1),
        sales_close_at=now + timedelta(days=9),
        is_published=True,
    )


@pytest.fixture
def ticket_type(event):
    return TicketType.objects.create(
        event=event,
        name="Standard",
        price_minor=1000,
        quantity_total=10,
        quantity_available=10,
        max_per_order=4,
    )


@pytest.fixture
def verified_user(db):
    return User.objects.create_user(
        email="buyer@example.com",
        full_name="Test Buyer",
        password="s3cure-passphrase!",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def unverified_user(db):
    return User.objects.create_user(
        email="unverified@example.com",
        full_name="Not Confirmed",
        password="s3cure-passphrase!",
    )


@pytest.fixture(autouse=True)
def clean_queue(request):
    """Redis is process-wide state; wipe each event's line between tests."""
    yield
    if "event" in request.fixturenames:
        try:
            queue.reset_queue(request.getfixturevalue("event").id)
        except Exception:
            pass
