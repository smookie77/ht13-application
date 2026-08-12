# Ticketing Platform — Hack TUES 13 / TUES Fest 2027 application task

A ticket sales system built to survive the moment sales open: hundreds of people
hitting *Buy* at the same second for a limited number of tickets.

## The core problem

Everything else here is routine CRUD. The interesting requirement is:

> fair (first to ask is first to get), never oversell, never fall over under load

This is solved by **separating asking from allocating**:

```
POST /api/reservations
   ├─ INSERT Reservation(status=QUEUED)      one cheap write
   ├─ RPUSH queue:event:<id> <reservation_id>
   └─ 202 Accepted + reservation_id          responds in milliseconds

allocator process (single consumer, BLPOP loop)
   ├─ pops strictly in arrival order          → FIFO fairness
   ├─ UPDATE ticket_type
        SET quantity_available = quantity_available - 1
        WHERE id = %s AND quantity_available > 0   → oversell impossible
   ├─ pushes the result over WebSocket        → live queue position
   └─ queues a Celery job: PDF → object storage → email
```

Why this shape:

- **Fairness comes from a single consumer**, not from locks. There is no
  `SELECT FOR UPDATE` contention when 500 requests land at once.
- **The conditional UPDATE is an independent second guarantee.** Even if two
  allocators were started by mistake, the database still cannot go negative — a
  `CheckConstraint` backs it up.
- **The web tier never touches the stock counter**, so a traffic spike costs one
  INSERT and one Redis push per user.
- Reservations carry a hold TTL, so an abandoned checkout returns its ticket to
  the pool. This is also the seam where Stripe drops in later.

Verified on Postgres: 200 concurrent buyers against 10 tickets → exactly 10
succeed, 0 remain.

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| API | Django 5.2 + DRF | ORM-only queries, so no SQL injection surface; batteries included |
| SPA | Next.js 15 + TypeScript + Tailwind | SSR for the landing page's SEO, trivial Vercel deploy |
| Database | PostgreSQL 16 | Conditional UPDATE + check constraints as the oversell guarantee |
| Queue / cache / pub-sub | Redis | FIFO list, Channels layer and Celery broker in one component |
| Real-time | Django Channels (WebSocket) | Pushes both the live counter and queue position |
| Background jobs | Celery | PDF rendering, uploads and email stay off the request path |
| PDF | WeasyPrint + qrcode | HTML/CSS template → a ticket that actually looks designed |
| Email | Resend | Generous free tier, plain REST API, no sandbox approval delay (unlike SES) |
| Object storage | Cloudflare R2 | S3-compatible, zero egress fees; **private bucket + presigned URLs** |
| Hosting | Railway | Postgres + Redis add-ons and multiple process types from one repo |

Email and storage sit behind interfaces in `apps/integrations/`, so swapping
Resend for SES is one class.

## Layout

```
backend/
  config/            settings/{base,dev,prod,test}.py, asgi.py, celery.py
  apps/
    events/          Event, TicketType — the public catalogue (read path)
    ticketing/       reservations, queue, allocator, PDF/email jobs
    accounts/        auth + email verification
    integrations/    email / storage / pdf adapters
frontend/            Next.js App Router SPA
docker-compose.yml   postgres, redis, api (+ worker, allocator)
```

Views stay thin; business logic lives in `services.py` and read helpers in
`selectors.py`, so the rules are testable without going through HTTP.

## Running locally

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY
docker compose up -d db redis

cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --open-now
.venv/bin/python manage.py runserver

cd ../frontend && npm install && npm run dev
```

API at `http://localhost:8000/api/`, docs at `/api/docs/`, SPA at
`http://localhost:3000`.

## Security

- All data access goes through the Django ORM — queries are parameterised.
- No secret is committed. `.env` is git-ignored; production reads platform env vars.
- Ticket PDFs live in a private bucket and are served via short-lived presigned
  URLs, checked against the requesting user.
- Production settings enable HSTS, secure cookies and SSL redirect.

## Status

- [x] Project scaffold, Docker setup, settings split
- [x] Event / TicketType models, read-only catalogue API, admin, demo seed
- [x] Oversell guarantee proven under concurrency
- [ ] Auth + email verification
- [ ] Reservation queue + allocator
- [ ] WebSocket live counter and queue position
- [ ] PDF ticket → R2 → email
- [ ] Deploy
