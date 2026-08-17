# Ticketing Platform — Hack TUES 13 / TUES Fest 2027 application task

A ticket sales system built to survive the moment sales open: hundreds of people
hitting *Buy* at the same second for a limited number of tickets.

## The core problem

Everything else here is routine CRUD. The interesting requirement is:

> fair (first to ask is first to get), never oversell, never fall over under load

This is solved by **separating asking from allocating**:

```
POST /api/reservations/
   ├─ INSERT Reservation(status=queued)       one cheap write
   ├─ RPUSH queue:event:<id> <public_id>
   └─ 202 Accepted + public_id                responds in milliseconds

allocator process (single consumer, BLPOP loop)
   ├─ pops strictly in arrival order          → FIFO fairness
   ├─ UPDATE events_tickettype
        SET quantity_available = quantity_available - n
        WHERE id = %s AND quantity_available >= n   → oversell impossible
   ├─ pushes the verdict over WebSocket       → live queue position
   └─ 10-minute hold, then payment
```

Why this shape:

- **Fairness comes from a single consumer**, not from locks. There is no
  `SELECT FOR UPDATE` contention when 500 requests land at once.
- **The conditional UPDATE is an independent second guarantee.** Even if two
  allocators were started by mistake, the database still cannot go negative — a
  `CheckConstraint` backs it up.
- **The web tier never touches the stock counter**, so a traffic spike costs one
  INSERT and one Redis push per user.
- Holds expire, so an abandoned checkout returns its ticket to the pool. That is
  also the seam where Stripe drops in later.

### Queue position without a message per person

Two Redis counters per event: `seq` (incremented when someone joins) and
`served` (incremented when the allocator pops). A buyer's position is
`sequence - served`. One broadcast of `served` therefore updates *everybody's*
position at once — O(1) messages per allocation instead of O(queue length).

Verified end to end: 150 concurrent buyers racing for 25 tickets → all 150
accepted with 202, exactly 25 allocated, stock lands on 0, and the winners are
precisely the first 25 to ask.

### Connections are pooled, not persistent

The first load run died on `FATAL: sorry, too many clients already`: with
`CONN_MAX_AGE` every worker thread holds its own Postgres connection until it
times out, and a spike exhausts the server — the exact failure this design is
meant to survive. The database now uses psycopg's bounded pool
(`OPTIONS["pool"]`), which caps what one process can consume and returns
connections immediately.

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| API | Django 5.2 + DRF (ASGI/Daphne) | ORM-only queries, so no SQL injection surface; batteries included |
| SPA | Next.js 16 + TypeScript + Tailwind | SSR for the landing page's SEO; standalone output keeps the image small enough for a Pi |
| Database | PostgreSQL 16 | Conditional UPDATE + check constraints as the oversell guarantee |
| Queue / cache / pub-sub | Redis | FIFO list, Channels layer and Celery broker in one component |
| Real-time | Django Channels (WebSocket) | Pushes both the live counter and queue position |
| Background jobs | Celery + beat | PDF rendering, uploads, email and expiring stale holds |
| PDF | WeasyPrint + qrcode | HTML/CSS template → a ticket that actually looks designed |
| Email | Resend | Generous free tier, plain REST API, no sandbox approval delay (unlike SES) |
| Object storage | Cloudflare R2 | S3-compatible, zero egress fees — every buyer downloads their ticket, often at the door; **private bucket + presigned URLs** |
| Hosting | Raspberry Pi 4 + Cloudflare Tunnel | Self-hosted; the tunnel gives public HTTPS with no port forwarding, static IP or open firewall port |

Email and storage sit behind interfaces in `apps/integrations/`, so swapping
Resend for SES is one class plus one settings line.

## Layout

```
backend/
  config/            settings/{base,dev,prod,test}.py, asgi.py, celery.py
  apps/
    accounts/        custom email-keyed user, signed verification tokens
    events/          Event, TicketType — the public catalogue (read path)
    ticketing/       reservations, Redis queue, allocator, consumers, tasks
    integrations/    swappable adapters: email, object storage, PDF
  templates/         the ticket PDF, as HTML/CSS
  tests/             pytest, incl. concurrency and fairness proofs
  scripts/           e2e_check.py — full-stack smoke test
frontend/            Next.js App Router SPA
docker-compose.yml       local dev: postgres, redis, api, allocator, worker, beat
docker-compose.prod.yml  the Pi: everything above plus web and cloudflared
```

Views stay thin; business rules live in `services.py`, read helpers in
`selectors.py`, Redis mechanics in `queue.py`, push in `realtime.py`. Each is
testable without going through HTTP.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/events/` `/api/events/<slug>/` | Public catalogue |
| GET | `/api/events/<slug>/availability/` | Stock snapshot |
| GET | `/api/auth/csrf/` | Bootstraps the CSRF cookie |
| POST | `/api/auth/register/` `/verify/` `/resend-verification/` | Email confirmation flow |
| POST | `/api/auth/login/` `/logout/` · GET `/api/auth/me/` | Session auth |
| POST | `/api/reservations/` | Join the queue → **202** |
| GET | `/api/reservations/` `/api/reservations/<uuid>/` | Own orders only |
| POST | `/api/reservations/<uuid>/confirm/` `/cancel/` | Simulated payment / release |
| GET | `/api/tickets/` `/api/tickets/<code>/` | Own issued tickets |
| GET | `/api/tickets/<code>/download/` | PDF — redirects to a signed URL |
| POST | `/api/tickets/check-in/` | Door scan, **staff only** |
| WS | `/ws/events/<slug>/` | Live counters, public |
| WS | `/ws/reservations/<uuid>/` | Live queue position, owner only |

Interactive docs at `/api/docs/`.

## The ticket itself

Paying triggers a Celery task that renders one A5 PDF per admission, uploads it
to object storage and emails it as an attachment. The buyer can re-download it
from `/account` at any time.

WeasyPrint over ReportLab: the ticket is an HTML/CSS template
(`templates/tickets/ticket.html`), so redesigning it is a template edit rather
than moving drawing coordinates, and it can be previewed in a browser.

The QR encodes `/check-in/<code>`, which a steward opens on their phone.
Scanning alone admits nobody — the check-in endpoint requires staff
credentials, and a second scan of the same ticket returns **409 Conflict**
rather than quietly succeeding. Codes are 20 characters of a confusable-free
base32 alphabet (~93 bits), so they can be read aloud at the door and still
cannot be guessed.

Each of the three steps — mint, upload, email — is separately idempotent, so a
retried task never issues a second ticket. Storage failures abort the task; an
email failure does not undo an already-stored ticket, it just retries.

## Running locally

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY
docker compose up -d db redis

cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --open-now
.venv/bin/python manage.py runserver          # ASGI, serves HTTP + WebSocket

# in another shell — the queue does not move without it
.venv/bin/python manage.py run_allocator --event hack-tues-13

cd ../frontend && cp .env.local.example .env.local && npm install && npm run dev
```

API at `http://localhost:8000/api/`, SPA at `http://localhost:3000`.
In development, verification emails are printed to the Django server log.

## Testing

```bash
cd backend
.venv/bin/python -m pytest        # 47 tests, incl. concurrency and fairness
.venv/bin/python scripts/e2e_check.py   # full stack, against a running server
```

The suite runs against real Postgres and Redis rather than mocks, because the
claims being tested are about actual concurrent behaviour.

### Walking through it by hand

Three processes have to be up: the API, the allocator and the SPA. Then, at
`http://localhost:3000`:

1. **Register** at `/register`. The account starts unverified.
2. **Confirm the email.** No mail is really sent in development — print the link
   instead:
   ```bash
   .venv/bin/python manage.py verification_link you@example.com
   # or skip the click entirely:
   .venv/bin/python manage.py verification_link you@example.com --verify
   ```
3. **Buy.** `/tickets` → *Get in line*. You land on the queue page with a live
   position. With an idle queue you are served in under a second; to actually
   see the queue, fill it first:
   ```bash
   .venv/bin/python -c "
   import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup()
   from apps.events.models import Event
   from apps.ticketing import queue
   e = Event.objects.get(slug='hack-tues-13')
   for i in range(50): queue.enqueue(e.id, f'ghost-{i}')
   print('50 people ahead of you')"
   ```
   Stop the allocator first, join the queue, then start it again and watch the
   number count down without a refresh.
4. **Watch the counter move.** Open the landing page in a second window and sell
   some stock from a shell — the number changes in both windows with no refresh:
   ```bash
   .venv/bin/python -c "
   import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup()
   from apps.events.models import TicketType
   TicketType.objects.filter(name='Standing').update(quantity_available=7)"
   ```
5. **Pay** — simulated, nothing is charged. The PDF is rendered, stored and
   "emailed" (printed to the server log).
6. **Download** from `/account`, and check the PDF has your name and a QR code.
7. **Check in at the door.** Grant yourself staff rights, then open the URL the
   QR encodes:
   ```bash
   .venv/bin/python manage.py make_staff you@example.com
   ```
   `/check-in/<code>` → *Verify and admit*. Scan it a second time: it reports the
   ticket as already used rather than admitting twice.

To start over: `seed_demo --open-now` resets the stock.

## Security

- All data access goes through the Django ORM — queries are parameterised.
- No secret is committed. `.env` is git-ignored; production reads platform env vars.
- Sessions live in an httpOnly cookie, so an XSS bug cannot read the credential.
  DRF marks its views `csrf_exempt` and only re-checks CSRF for authenticated
  requests, so the anonymous auth endpoints opt back in with `@csrf_protect`.
- Ownership-based authorisation: reservation queries are filtered to the
  requesting user, so another person's UUID simply does not resolve (404).
- A confirmed email is required to take a ticket, enforced server-side.
- Reservation creation is rate limited, and one person may hold one in-flight
  request per event — a fairness rule as much as an abuse control.
- WebSockets go through `AllowedHostsOriginValidator`; the reservation socket
  refuses the handshake outright for anyone but the owner.
- Auth responses are deliberately uniform, so neither registration nor login can
  be used to discover which addresses have accounts.
- Production settings enable HSTS, secure cookies and SSL redirect.

## Status

- [x] Project scaffold, Docker setup, settings split
- [x] Event / TicketType models, read-only catalogue API, admin, demo seed
- [x] Landing, event, tickets and contact pages
- [x] Auth + email verification
- [x] Reservation queue + allocator
- [x] WebSocket live counter and queue position
- [x] PDF ticket → object storage → email, with authenticated re-download
- [x] QR code + staff check-in (bonus)
- [x] Admin panel for events, orders and tickets (bonus)
- [x] Deploy configuration for Raspberry Pi 4 + Cloudflare — see [DEPLOY.md](DEPLOY.md)
- [ ] Deployed to a live URL (needs the Cloudflare account and the device)

Not attempted: reserved seating and Stripe. The models carry a `has_seating`
flag and the ticket template already has a seat slot, and the payment step is a
single service function, so both are additive rather than rewrites.
