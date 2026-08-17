"""End-to-end smoke check against a running API.

Exercises the real HTTP surface the SPA uses: register, verify, log in, join
the queue, get allocated by the allocator process, then pay. Also asserts the
fairness property under concurrency.

This script *is* the allocator for the duration of the run - it drains the
queue itself so it can assert on the state in between. Stop any separate
`run_allocator` process first, or the two will race for the same queue.

Usage (with the API and Redis up):
    .venv/bin/python scripts/e2e_check.py
"""

import asyncio
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import django
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.accounts import tokens  # noqa: E402
from apps.events.models import Event, TicketType  # noqa: E402
from apps.ticketing import queue  # noqa: E402
from apps.ticketing.models import Reservation, ReservationStatus  # noqa: E402

API = "http://localhost:8000"
PASSWORD = "s3cure-passphrase!"
User = get_user_model()

ok = lambda msg: print(f"  PASS  {msg}")  # noqa: E731


def client_for(email: str) -> httpx.Client:
    """Log in and return a client carrying the session and CSRF header."""
    c = httpx.Client(base_url=API, timeout=15)
    c.get("/api/auth/csrf/")
    c.headers["X-CSRFToken"] = c.cookies["csrftoken"]
    c.headers["Referer"] = API
    response = c.post("/api/auth/login/", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    c.headers["X-CSRFToken"] = c.cookies["csrftoken"]
    return c


def test_auth_flow():
    print("\n[1] Registration and email verification")
    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"

    c = httpx.Client(base_url=API, timeout=15)
    c.get("/api/auth/csrf/")
    c.headers.update({"X-CSRFToken": c.cookies["csrftoken"], "Referer": API})

    r = c.post(
        "/api/auth/register/",
        json={"email": email, "full_name": "E2E Tester", "password": PASSWORD},
    )
    assert r.status_code == 201, r.text
    ok("registered")

    user = User.objects.get(email=email)
    assert not user.is_email_verified
    ok("account starts unverified")

    # An unverified account must not be able to take a ticket.
    logged_in = client_for(email)
    ticket_type = TicketType.objects.filter(name="Standing").first()
    r = logged_in.post("/api/reservations/", json={"ticket_type_id": ticket_type.pk})
    assert r.status_code == 403, f"unverified user got {r.status_code}"
    ok("unverified user is blocked from reserving (403)")

    # Verify using the same token the email would carry.
    r = logged_in.post(
        "/api/auth/verify/", json={"token": tokens.make_verification_token(user)}
    )
    assert r.status_code == 200, r.text
    user.refresh_from_db()
    assert user.is_email_verified
    ok("email confirmed via signed token")

    r = logged_in.post("/api/auth/verify/", json={"token": "tampered.token.value"})
    assert r.status_code == 400
    ok("tampered token rejected (400)")

    return email


def test_fairness_under_load(tier_name="VIP", stock=5, buyers=40):
    print(f"\n[2] {buyers} concurrent buyers racing for {stock} '{tier_name}' tickets")
    event = Event.objects.get(slug="hack-tues-13")
    tier = TicketType.objects.get(event=event, name=tier_name)

    TicketType.objects.filter(pk=tier.pk).update(quantity_available=stock)
    Reservation.objects.filter(event=event).delete()
    queue.reset_queue(event.id)

    emails = []
    for i in range(buyers):
        email = f"load-{uuid.uuid4().hex[:8]}-{i}@example.com"
        User.objects.create_user(
            email=email,
            full_name=f"Buyer {i}",
            password=PASSWORD,
            email_verified_at=timezone.now(),
        )
        emails.append(email)

    def buy(email):
        c = client_for(email)
        r = c.post("/api/reservations/", json={"ticket_type_id": tier.pk})
        c.close()
        return r.status_code

    with ThreadPoolExecutor(max_workers=25) as pool:
        codes = list(pool.map(buy, emails))

    accepted = codes.count(202)
    assert accepted == buyers, f"only {accepted}/{buyers} accepted: {set(codes)}"
    ok(f"all {buyers} requests accepted with 202 (nobody rejected at the door)")

    remaining = TicketType.objects.get(pk=tier.pk).quantity_available
    assert remaining == stock, (
        f"stock already moved ({remaining} left, expected {stock}). "
        "Is a separate `manage.py run_allocator` running? This script drains "
        "the queue itself and cannot share it."
    )
    ok("no stock touched yet - the web tier never decrements")
    assert queue.queue_length(event.id) == buyers
    ok(f"{buyers} people waiting in the Redis line")

    return event, tier, stock, buyers


def drain_queue(event):
    """Do exactly what `manage.py run_allocator` does, inline."""
    from apps.ticketing import services

    served = 0
    while (public_id := queue.pop_blocking(event.id, timeout=1)) is not None:
        services.allocate(Reservation.objects.get(public_id=public_id))
        queue.mark_served(event.id)
        served += 1
    return served


def check_allocation(event, tier, stock, buyers):
    print("\n[3] Allocator drains the queue")
    served = drain_queue(event)
    assert served == buyers
    ok(f"allocator served all {buyers} in order")

    reservations = list(Reservation.objects.filter(event=event).order_by("sequence"))
    allocated = [r for r in reservations if r.status == ReservationStatus.ALLOCATED]
    rejected = [r for r in reservations if r.status == ReservationStatus.REJECTED]

    assert len(allocated) == stock, f"{len(allocated)} allocated, expected {stock}"
    ok(f"exactly {stock} allocated - no oversell")
    assert TicketType.objects.get(pk=tier.pk).quantity_available == 0
    ok("stock counter landed exactly on zero")
    assert len(rejected) == buyers - stock
    ok(f"{len(rejected)} told it sold out before their turn")

    winners = [r.sequence for r in allocated]
    assert winners == sorted(r.sequence for r in reservations)[:stock]
    ok("the winners are exactly the first to ask - FIFO holds")

    return allocated[0]


def check_payment(reservation):
    print("\n[4] Simulated payment")
    c = client_for(reservation.user.email)

    r = c.get(f"/api/reservations/{reservation.public_id}/")
    assert r.status_code == 200 and r.json()["status"] == "allocated"
    ok("buyer sees their allocated reservation")

    r = c.post(f"/api/reservations/{reservation.public_id}/confirm/")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    ok("payment confirmed")

    check_ticket_delivery(c, reservation)

    # Someone else must not be able to read it.
    other = User.objects.exclude(pk=reservation.user.pk).filter(
        email__startswith="load-"
    ).first()
    other_client = client_for(other.email)
    r = other_client.get(f"/api/reservations/{reservation.public_id}/")
    assert r.status_code == 404, f"leaked another user's order: {r.status_code}"
    ok("another user cannot read it (404)")


def check_ticket_delivery(client, reservation):
    """The PDF path: minted, rendered, stored and downloadable by its owner."""
    print("\n[5] PDF ticket, storage and delivery")
    from apps.ticketing import issuing

    # Celery is not running in this check, so the task body is invoked directly.
    tickets = issuing.issue_tickets(Reservation.objects.get(pk=reservation.pk))
    assert len(tickets) == reservation.quantity
    ok(f"{len(tickets)} ticket(s) minted, one per admission")

    again = issuing.issue_tickets(Reservation.objects.get(pk=reservation.pk))
    assert {t.code for t in again} == {t.code for t in tickets}
    ok("re-running the task is idempotent - no duplicate tickets")

    for ticket in tickets:
        ticket.refresh_from_db()
        assert ticket.pdf_key, "ticket was never stored"
        assert ticket.emailed_at is not None, "ticket was never emailed"
    ok("every ticket is stored in object storage and marked as sent")

    code = tickets[0].code
    r = client.get(f"/api/tickets/{code}/download/")
    assert r.status_code == 200, r.status_code
    assert r.content.startswith(b"%PDF-"), r.content[:20]
    ok(f"owner downloaded a real PDF ({len(r.content)} bytes)")

    other = User.objects.exclude(pk=reservation.user.pk).filter(
        email__startswith="load-"
    ).first()
    r = client_for(other.email).get(f"/api/tickets/{code}/download/")
    assert r.status_code == 404, f"leaked another user's ticket: {r.status_code}"
    ok("another user cannot download it (404)")

    r = client.post("/api/tickets/check-in/", json={"code": code})
    assert r.status_code == 403, r.status_code
    ok("a non-staff buyer cannot check tickets in (403)")

    return code


async def check_websocket(event_slug, tier_id, tier_available):
    """ORM objects are resolved by the caller: this coroutine runs in an async
    context, where synchronous queries are not allowed."""
    print("\n[6] WebSocket live counter")
    import json

    import websockets

    async with websockets.connect(f"ws://localhost:8000/ws/events/{event_slug}/") as ws:
        snapshot = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        assert snapshot["type"] == "availability.update"
        before = snapshot["payload"]["tickets_available"]
        ok(f"connected and received a snapshot immediately ({before} left)")

        # Push a change the way the allocator would.
        from asgiref.sync import sync_to_async

        from apps.ticketing import realtime

        await sync_to_async(TicketType.objects.filter(pk=tier_id).update)(
            quantity_available=tier_available - 7
        )
        fresh = await sync_to_async(
            lambda: Event.objects.prefetch_related("ticket_types").get(slug=event_slug)
        )()
        await sync_to_async(realtime.broadcast_availability)(fresh)

        update = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        after = update["payload"]["tickets_available"]
        assert after == before - 7, f"expected {before - 7}, got {after}"
        ok(f"push received without polling ({before} -> {after})")
        assert "now_serving" in update["payload"]
        ok("broadcast carries now_serving, so every waiter recomputes position")

    # Closing before accept() means Channels denies the handshake outright, so
    # an unauthenticated reservation socket never opens at all.
    try:
        async with websockets.connect(
            f"ws://localhost:8000/ws/reservations/{uuid.uuid4()}/"
        ):
            raise AssertionError("anonymous reservation socket was accepted")
    except websockets.exceptions.InvalidStatus as exc:
        assert exc.response.status_code == 403, exc.response.status_code
        ok("anonymous reservation socket refused at handshake (403)")


def main():
    test_auth_flow()
    event, tier, stock, buyers = test_fairness_under_load()
    winner = check_allocation(event, tier, stock, buyers)
    check_payment(winner)

    standing = TicketType.objects.get(event=event, name="Standing")
    asyncio.run(
        check_websocket(event.slug, standing.pk, standing.quantity_available)
    )
    print("\nAll end-to-end checks passed.\n")


if __name__ == "__main__":
    main()
