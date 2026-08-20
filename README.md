# Webhook Delivery System (WDS)

An async webhook delivery engine — the kind of thing you'd put in front of any product that needs to fan events out to third-party URLs reliably. Producers push events in, subscribers register the URLs they want to receive them on, and the system takes care of signing, retrying, giving up gracefully, and telling you *why* a delivery failed.

Built with FastAPI, Celery, PostgreSQL, Redis, and Next.js. Failure analysis is done by an LLM (Groq/Llama) so a dead delivery comes with an actual explanation instead of just a stack trace.

**Live demo:** [webhook-delivery-system.vercel.app/demo](https://webhook-delivery-system.vercel.app/demo)
**Dashboard:** [webhook-delivery-system.vercel.app/dashboard](https://webhook-delivery-system.vercel.app/dashboard)

> Backend is deployed on Render's free tier, which spins down when idle — the first request after a while can take 30–60s to come back. Don't panic, it's not broken.

---

## What it actually does

There are two kinds of API consumers:

- **Producers** — the systems generating events (e.g. an orders service saying "order.created").
- **Subscribers** — the systems that want to be notified, by registering a target URL for a given `event_type`.

When a producer POSTs an event:

1. The event is deduplicated by `idempotency_key` — firing the same key twice returns the same `event_id` and does **not** queue a second delivery.
2. It's matched against active subscriptions for that `event_type` (optionally scoped to a specific producer — see below).
3. A `DeliveryAttempt` row is created per matching subscription, and a Celery task is dispatched to actually deliver it.
4. The API responds `202 Accepted` immediately — delivery happens in the background, so producers never wait on a slow or dead subscriber.

Delivery itself:

- The payload is signed with HMAC-SHA256 using a per-subscriber secret, sent as `X-Webhook-Signature: sha256=<hex>`, so subscribers can verify authenticity independently.
- On success (2xx), the attempt is marked `delivered`.
- On failure (non-2xx, timeout, connection error), it's retried with exponential backoff + jitter: roughly 30s → 60s → 120s → 240s across 5 attempts.
- After the 5th failed attempt, it lands in the **dead-letter queue** and an AI analysis is kicked off automatically to explain what likely went wrong and how to fix it.
- Failed deliveries can be manually retried from the dashboard, which resets the attempt counter and clears the previous AI analysis.

Subscriptions can optionally be scoped to a specific `producer_id`. An unscoped subscription receives events from *any* producer for that event type; a scoped one only receives events from the producer it was registered against.

---

## Architecture

```
Producer
    │
    ▼
POST /api/v1/events
    │
    ├── Idempotency check (by idempotency_key)
    │
    ├── Match active subscriptions for event_type (+ optional producer scope)
    │
    ├── Create DeliveryAttempt rows (status=pending)
    │
    └── Celery: deliver_webhook.delay(attempt_id) ──► Worker
                                                          │
                                              ┌───────────┴───────────┐
                                              │                       │
                                        HTTP 2xx                HTTP 4xx/5xx / timeout
                                              │                       │
                                        status=delivered        attempt_number < 5?
                                              │                  yes │      no │
                                        Pub/Sub notify         retry (backoff)  status=dead
                                                                     │              │
                                                              Pub/Sub notify  analyze_failure.delay()
                                                                                    │
                                                                              Groq AI analysis
                                                                              stored in DB
                                                                                    │
                                                                              Pub/Sub notify
```

The dashboard subscribes to the same Pub/Sub channel via Server-Sent Events, so status changes show up live without polling.

### Why each Celery task creates its own DB engine

`deliver_webhook` and `analyze_failure` each build a fresh SQLAlchemy async engine and dispose of it at the end of the task, instead of sharing a connection pool. `asyncpg` connections are bound to the event loop that created them, and every Celery task runs inside its own `asyncio.run()` call — reusing a pooled connection across tasks throws "attached to a different loop" errors. The tradeoff is a new engine per task rather than pooled reuse; fine at current volume, worth revisiting if delivery throughput grows a lot.

### Crash recovery

If a Celery worker is killed mid-delivery, the attempt can get stuck in `delivering`. On startup, the app resets any attempt that's been sitting in `delivering` for more than 2x the delivery timeout back to `failed`. This is deliberately **not** auto-requeued — it needs a manual retry from the dashboard, to avoid retry storms right after a crash.

---

## Features

**Delivery engine**
- Async fan-out — events accepted with `202` immediately, delivery happens in the background
- Exponential backoff with jitter, 5 attempts before dead-lettering
- Dead-letter queue with one-click manual retry
- HMAC-SHA256 payload signing on every request
- Idempotency-key deduplication
- Producer-scoped or global subscriptions
- `acks_late` + `reject_on_worker_lost` on Celery, so tasks re-queue if a worker dies mid-job
- Stuck-delivery recovery on startup (see above)

**Observability**
- Redis Pub/Sub → Server-Sent Events pushes delivery state changes straight to the dashboard, no polling
- Per-attempt detail: response code/body, duration, error history (previous failure is preserved in the error message when a retry also fails), retry schedule
- Dashboard stats: total events, attempt breakdown by status, success rate
- Prometheus metrics via `prometheus-fastapi-instrumentator` (exposed at `/metrics`) for standard HTTP request/latency metrics
- Custom delivery metrics pushed to a **Pushgateway** from inside the Celery workers (since those are short-lived processes, not scrape targets): attempt outcomes, attempt-number-to-outcome histograms, delivery duration histograms, retry delay histograms, AI analysis counts by category/severity
- A provisioned Grafana dashboard (`wds-overview`) covering request rate, p95 latency, 5xx rate, delivery outcomes by status, retries by event type, delivery duration p95, dead-letter count, and AI analyses by severity

**AI failure analysis**
- Every dead-lettered attempt is automatically analyzed by Groq (Llama 3.1 8B)
- Returns `failure_category`, `explanation`, `suggested_fix`, `confidence_score`, `severity`
- Falls back to a generic "check the logs" analysis if the Groq call fails, so a missing key or an outage never blocks the delivery pipeline itself

**Auth**
- API-key auth for both producers (`pk_...`) and subscribers (`wh_...`), issued once on registration
- Subscribers additionally get a signing secret (shown once) to verify `X-Webhook-Signature`
- Subscriptions are scoped to the key holder — only the owning subscriber can create or list their own

**Infra**
- One `docker compose up` brings up Postgres, Redis, backend, Celery worker, mock subscriber, frontend, Pushgateway, Prometheus, and Grafana
- `render.yaml` deploys Postgres, Redis, backend (with embedded worker), and the mock subscriber on Render as a single blueprint
- Mock subscriber service for local testing: `/webhook` (200), `/webhook/fail` (500), `/webhook/slow` (60s hang, for testing timeout handling)
- Correlation IDs (`x-request-id`) threaded through HTTP requests and into Celery tasks via `structlog` context vars, so a single delivery can be traced across the API call and both background tasks in the logs

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13) |
| Task queue | Celery 5 |
| Database | PostgreSQL 16 + SQLAlchemy 2 (async, via asyncpg) |
| Cache / broker | Redis 7 |
| Frontend | Next.js 15 + React 19 |
| HTTP client | httpx (async) |
| AI analysis | Groq API — Llama 3.1 8B |
| Metrics | prometheus-fastapi-instrumentator + prometheus-client (Pushgateway) |
| Dashboards | Grafana, provisioned from `grafana/` |
| Logging | structlog (JSON, correlation-id aware) |
| Containerization | Docker + Docker Compose |
| Deployment | Render (API + worker + Postgres + Redis) and Vercel (frontend) |
| Load testing | k6 |

---

## API reference

### Producers
```
POST   /api/v1/producers                            Register a producer → returns api_key (once)
GET    /api/v1/producers                             List producers
```

### Subscribers
```
POST   /api/v1/subscribers                           Register a subscriber → returns api_key + secret (once)
GET    /api/v1/subscribers                            List subscribers
POST   /api/v1/subscribers/{id}/subscriptions        Register a target URL for an event type  [auth: x-api-key]
GET    /api/v1/subscribers/{id}/subscriptions         List a subscriber's subscriptions        [auth: x-api-key]
```

### Events
```
POST   /api/v1/events                                 Ingest an event → 202 Accepted  [auth: x-api-key, producer]
GET    /api/v1/events                                  List events
GET    /api/v1/events/{id}                             Get a single event
```

### Dashboard
```
GET    /api/v1/dashboard/stats                        Overview stats
GET    /api/v1/dashboard/delivery-attempts             List attempts (filter: ?status=)
GET    /api/v1/dashboard/delivery-attempts/{id}        Attempt detail + AI analysis
POST   /api/v1/dashboard/delivery-attempts/{id}/retry  Manually retry a failed/dead attempt
GET    /api/v1/dashboard/dead-letter                   Everything currently dead-lettered
GET    /api/v1/dashboard/stream                        SSE stream of live delivery events
```

### Ops
```
GET    /health                                         Liveness check
GET    /metrics                                        Prometheus metrics (HTTP-level, via instrumentator)
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     producers, subscribers, events, dashboard (incl. SSE)
│   │   ├── core/                 config (pydantic-settings), security (API key deps), logging
│   │   ├── db/                   SQLAlchemy async engine/session, declarative base
│   │   ├── models/                Producer, Subscriber, Subscription, Event, DeliveryAttempt, AIFailureAnalysis
│   │   ├── schemas/               Pydantic request/response models
│   │   ├── services/              producer_service, subscriber_service, event_service, delivery_service
│   │   ├── workers/
│   │   │   ├── celery_app.py      Celery config — acks_late, reject_on_worker_lost, etc.
│   │   │   ├── delivery_worker.py Core delivery loop — HTTP call, signing, retry scheduling, Pub/Sub
│   │   │   ├── ai_worker.py       Groq failure analysis task
│   │   │   └── metrics.py         Pushgateway metric pushes from within worker tasks
│   │   └── main.py                FastAPI app, CORS, correlation-id middleware, startup recovery
│   ├── tests/                     pytest-asyncio suite (hits a real Postgres container, not mocks)
│   ├── Dockerfile
│   └── start.sh                   Starts the embedded Celery worker + uvicorn in one container
├── frontend/
│   ├── app/
│   │   ├── dashboard/              Overview, Events, Attempts (+ detail), Dead Letter, Subscribers
│   │   └── demo/                   Self-contained interactive scenario runner
│   └── lib/api.ts                  Typed fetch wrapper + shared types
├── mock-subscriber/                FastAPI server — /webhook, /webhook/fail, /webhook/slow
├── load-tests/                     k6 scripts — smoke, steady-state ingest/delivery, ramping, extreme load
├── grafana/                        Provisioned datasource (Prometheus) + the wds-overview dashboard
├── prometheus.yml                  Scrape config for the backend and the Pushgateway
├── docker-compose.yml              Full local stack, including the observability services
└── render.yaml                     Render deployment blueprint
```

---

## Getting started

### Prerequisites
- Docker + Docker Compose
- A [Groq](https://console.groq.com/) API key (optional — AI analysis just degrades to a generic message without it)

### Run locally

```sh
git clone https://github.com/SahilSonar-04/webhook-delivery-system
cd webhook-delivery-system

echo "GROQ_API_KEY=your-groq-key-here" > .env

docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Mock subscriber | http://localhost:9000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/admin) |
| Pushgateway | http://localhost:9091 |

### Run tests

```sh
docker compose exec backend pytest
```

Tests run against the real Postgres container (schema is dropped and recreated per test function), not an in-memory substitute — slower, but it catches things a mocked DB wouldn't.

### Load testing

k6 scripts live in `load-tests/`:

| Script | What it does |
|---|---|
| `smoke.js` | 1 VU hitting `/health` for 10s — sanity check that the stack is up |
| `ingest.js` | Ramping load (0 → 1000 VUs) against `/api/v1/events`, with thresholds on error rate and p95 latency |
| `ingest-extreme.js` | Same idea, pushed to 3000 VUs, for stress-testing ingestion |
| `delivery.js` | Constant-arrival-rate load (300 req/s for 60s) aimed at exercising the full delivery path |

```sh
k6 run load-tests/smoke.js
```

(These scripts have a hardcoded producer key from a specific deployment — swap `PROD_KEY` and `BASE_URL` for your own before running.)

---

## Environment variables

### Backend

```env
# Local Docker Compose only needs GROQ_API_KEY set via the root .env file —
# everything else below is hardcoded in docker-compose.yml for local dev.
# This full list is what the backend container needs regardless of how
# it's run, e.g. when configuring Render env vars for a real deployment.

ENVIRONMENT=development                      # or "production"
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/webhook_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=some-random-value
GROQ_API_KEY=your-groq-key                   # optional, degrades gracefully
FRONTEND_URL=https://your-frontend           # added to CORS origins in production
PUSHGATEWAY_URL=http://pushgateway:9091

# Delivery tuning (optional — these are the defaults)
MAX_RETRY_ATTEMPTS=5
BASE_RETRY_DELAY=30
MAX_RETRY_DELAY=7200
DELIVERY_TIMEOUT=30
```

### Frontend (build-time)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000     # or your deployed backend URL
NEXT_PUBLIC_MOCK_URL=http://localhost:9000    # or your deployed mock-subscriber URL
```

---

## Deployment

- **Backend, worker, Postgres, Redis**: deployed together via the Render Blueprint in `render.yaml`. The backend runs the Celery worker embedded in the same container (`RUN_EMBEDDED_WORKER=true`, see `start.sh`) rather than as a separate Render service, to stay within the free tier.
- **Mock subscriber**: also deployed on Render, used by the live demo page.
- **Frontend**: deployed separately to Vercel.
- **Prometheus / Grafana / Pushgateway**: only wired up in `docker-compose.yml` for local development — they aren't part of the Render blueprint, so metrics dashboards are a local-only feature right now.

There's no CI pipeline in this repo yet — tests are run manually (`docker compose exec backend pytest`) rather than on a GitHub Actions workflow.

---

## Demo

`/demo` on the frontend walks through every scenario without any manual setup — it provisions its own subscriber and producer against the live API and lets you fire real events:

| Scenario | What it shows |
|---|---|
| Successful delivery | HMAC-signed payload delivered on the first attempt |
| Failure + retry | Target returns 500 — watch exponential backoff and `next_retry_at` advance |
| Dead letter + AI | All 5 retries exhausted, Groq classifies the failure |
| Idempotency | Same `idempotency_key` fired twice — second call returns the identical `event_id` |
| No subscription | Event accepted (`queued=0`) but no subscriber is listening for that type |
| Timeout | Target hangs for 60s, worker cuts the connection at 30s and schedules a retry |

---

## License

MIT
