# Deploying to a Raspberry Pi 4 behind Cloudflare

Everything runs on the Pi in Docker. Cloudflare provides the public hostname,
TLS and DDoS protection through a **Tunnel**, so the Pi needs no port
forwarding, no static IP and no inbound firewall hole — `cloudflared` dials
*out* to Cloudflare and traffic comes back down that connection.

```
browser ──https──▶ Cloudflare edge ──tunnel──▶ cloudflared ──▶ web  (Next.js :3000)
                                                          └──▶ api  (Django :8000, HTTP + WebSocket)
                                                                  ├─▶ postgres
                                                                  └─▶ redis ◀── allocator, worker, beat
```

Ticket PDFs go to **Cloudflare R2**, not the SD card: object storage survives a
corrupted card, and R2 charges nothing for egress — which matters when every
buyer re-downloads their ticket at the door.

## Processes and their replica counts

| Service | Replicas | Why |
|---|---|---|
| api | scale freely | stateless |
| web | scale freely | stateless |
| worker | scale freely | Celery distributes work |
| **allocator** | **exactly 1** | fairness comes from one consumer popping the queue in arrival order |
| **beat** | **exactly 1** | two schedulers would fire every periodic task twice |

Running two allocators would still not oversell — the conditional `UPDATE`
holds — but strict first-come-first-served would be lost, which is the whole
point of the design.

## 0. Prepare the Pi

64-bit Raspberry Pi OS, 4 GB RAM or more.

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER && newgrp docker   # or just log out and back in
```

Two things worth doing before anything else:

- **Put Docker's data on an SSD, not the SD card.** Postgres writes constantly
  and SD cards die from it. A USB3 SSD is the single biggest reliability win
  here.
- **Give it swap.** The Next.js build is the memory peak; 2 GB of swap keeps it
  from being OOM-killed on a 4 GB Pi.
  ```bash
  sudo dphys-swapfile swapoff
  sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
  sudo dphys-swapfile setup && sudo dphys-swapfile swapon
  ```

## 1. Cloudflare Tunnel

In the Cloudflare dashboard: **Zero Trust → Networks → Tunnels → Create a
tunnel** (type `cloudflared`). Copy the token — that is the only credential the
Pi needs.

Add two public hostnames on the tunnel:

| Hostname | Service |
|---|---|
| `your-domain.com` | `http://web:3000` |
| `api.your-domain.com` | `http://api:8000` |

The service URLs use the compose service names, because `cloudflared` runs in
the same compose network.

**WebSockets:** enabled by default on Cloudflare, and the app sends a ping every
30 s so a quiet queue is not culled as an idle connection.

## 2. Cloudflare R2

1. **R2 → Create bucket**, name it `tickets`.
2. Leave public access **disabled**. Downloads go through the authenticated API,
   which redirects to a presigned URL valid for `TICKET_URL_TTL_SECONDS` (5 min).
3. **Manage API tokens → Create token**, permission *Object Read & Write*,
   scoped to that bucket only. Note the account ID, access key and secret.

## 3. Resend

1. Add your domain and publish the DKIM/SPF records Cloudflare DNS asks for.
2. Create a send-only API key.
3. Until the domain is verified Resend only delivers to your own address — worth
   knowing before assuming the app is broken.

## 4. Deploy

```bash
git clone <your-repo> ~/ticketing && cd ~/ticketing
cp .env.prod.example .env.prod
nano .env.prod          # fill in every blank; see the comments in the file

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

The first build takes **20–40 minutes** on a Pi: it compiles Python wheels and
builds the Next bundle natively on ARM. Later builds reuse the layer cache.

If that is too slow, build on your laptop and push instead:

```bash
docker buildx build --platform linux/arm64 -t <registry>/ticketing-api:latest backend --push
```

Then seed the event and create an admin:

```bash
cd ~/ticketing
dc() { docker compose -f docker-compose.prod.yml --env-file .env.prod "$@"; }

dc exec api python manage.py createsuperuser
dc exec api python manage.py seed_demo          # omit --open-now for a real sale
```

## 5. Verify

```bash
curl https://api.your-domain.com/api/health/          # {"status": "ok"}
curl https://api.your-domain.com/api/events/hack-tues-13/availability/
```

Then walk the real path once, in a browser: register → confirm the email → join
the queue → watch the counter move without refreshing → pay → confirm the PDF
arrives by email and downloads from `/account`.

Check the allocator is actually consuming:

```bash
dc logs -f allocator     # "Allocator serving 'hack-tues-13'"
dc exec redis redis-cli llen queue:event:1    # 0 when the queue is drained
```

## Operations

```bash
dc ps                       # what is running
dc logs -f api              # follow the API
dc restart allocator        # safe: queued reservations survive in Redis
dc exec api python manage.py migrate

# Backup - do this before the sale opens, not after
dc exec db pg_dump -U ticketing ticketing | gzip > ~/backup-$(date +%F).sql.gz
```

Redis persists with AOF, so a power cut does not drop a queue people are sitting
in — a real risk on a device with no UPS. Postgres holds the authoritative
record either way: a lost Redis queue costs pending positions, never a paid
ticket.

## Gotchas specific to this setup

- **`PUBLIC_API_URL` is baked into the frontend at build time.** `NEXT_PUBLIC_*`
  values are inlined into the browser bundle, so changing the API hostname means
  rebuilding `web`, not just restarting it.
- **`DJANGO_ALLOWED_HOSTS` must contain the API hostname.**
  `AllowedHostsOriginValidator` uses it to decide which origins may open a
  WebSocket; get it wrong and the live counter silently stops updating while the
  rest of the site looks fine.
- **The session cookie is cross-site** (`your-domain.com` → `api.your-domain.com`).
  Production settings already set `SameSite=None; Secure`, which requires HTTPS —
  provided by the tunnel.
- **Do not also forward ports on the router.** The tunnel is the only ingress;
  an open port would bypass Cloudflare entirely.
- **Pi thermals.** Under a sales spike the CPU will throttle without a heatsink
  or fan. Worth checking with `vcgencmd measure_temp` during a load test.
