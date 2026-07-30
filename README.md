# Webhook Delivery System

An async webhook delivery engine built with FastAPI, Celery, PostgreSQL, Redis, and Next.js, with AI-assisted failure analysis via Groq.

**Live demo:** [webhook-delivery-system.vercel.app/demo](https://webhook-delivery-system.vercel.app/demo)
**Dashboard:** [webhook-delivery-system.vercel.app/dashboard](https://webhook-delivery-system.vercel.app/dashboard)

> Deployed on Render's free tier — the backend can take 30–60s to respond on the first request after a period of inactivity. See [Deployment](#deployment) below.

---

## Overview

A fan-out system that accepts events from producers, matches them against subscriber registrations, and delivers signed payloads asynchronously with retries and a dead-letter queue. Built to survive worker crashes, network failures, and slow endpoints, with a dashboard to watch delivery status in real time.

---

## Features

### Delivery Engine
- Async fan-out — events are accepted immediately (202), delivery happens in the background via Celery
- Exponential backoff with jitter — ~30s, ~60s, ~120s, ~240s across 5 attempts
- Dead-letter queue for exhausted attempts, with manual retry from the dashboard
- HMAC-SHA256 payload signing — every request carries `X-Webhook-Signature: sha256=<hex>`
- Idempotency key deduplication — duplicate events with the same key don't create new delivery attempts
- `next_retry_at` stored per attempt so workers pick up retries at the right time
- `acks_late` + `reject_on_worker_lost` so tasks re-queue if a worker is killed mid-job
- Stuck-delivery recovery — attempts left in `delivering` for longer than 2x the timeout are reset to `failed` on startup (this requires a manual retry from the dashboard; it doesn't auto-requeue, to avoid retry storms after a crash)

### Observability
- Redis Pub/Sub + Server-Sent Events push delivery updates to the dashboard without polling
- Per-attempt detail — response code, body, duration, error history, retry schedule
- Dashboard stats — total events, attempt breakdown (delivered / failed / pending / dead), success rate

### AI Failure Analysis
- Groq (Llama 3.1) classifies every dead-letter attempt automatically
- Returns `failure_category`, `explanation`, `suggested_fix`, `confidence_score`, `severity`
- Falls back to a generic analysis if the Groq API call fails, so a bad key or outage doesn't block the delivery pipeline

### Auth
- API-key authentication — subscribers get a `wh_`-prefixed key on registration, shown once
- HMAC request signing lets subscribers verify payload integrity independently
- Subscriptions are scoped to the key-holder — only the owning subscriber can create or list their own subscriptions

### Infrastructure
- Docker Compose brings up Postgres, Redis, backend, Celery worker, mock subscriber, and the Next.js frontend in one command
- `render.yaml` for deployment on Render
- Async SQLAlchemy throughout, with `asyncpg`
- Mock subscriber service for local testing: `/webhook` (200), `/webhook/fail` (500), `/webhook/slow` (60s hang, used to test timeout handling)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13) |
| Task Queue | Celery 5 |
| Database | PostgreSQL 16 + SQLAlchemy (async) |
| Cache / Broker | Redis 7 |
| Frontend | Next.js 15 + React 19 |
| HTTP Client | httpx (async) |
| AI Analysis | Groq API — Llama 3.1 8B |
| Containerization | Docker + Docker Compose |
| Deployment | Render (API, worker, Postgres, Redis) + Vercel (frontend) |

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
    ├── Match active subscriptions for event_type
    │
    ├── Create DeliveryAttempt rows (status=pending)
    │        │
    │        └── flush → commit
    │
    └── Celery: deliver_webhook.delay(attempt_id) ──► Worker
                                                          │
                                              ┌───────────┴───────────┐
                                              │                       │
                                        HTTP success           HTTP failure / timeout
                                              │                       │
                                        status=delivered        attempt_number < 5?
                                              │                  yes │      no │
                                        Pub/Sub notify              retry   status=dead
                                                              (backoff delay)    │
                                                                           analyze_failure.delay()
                                                                                 │
                                                                           Groq AI analysis
                                                                           stored in DB
```

Each Celery task (`deliver_webhook`, `analyze_failure`) creates its own SQLAlchemy engine and disposes of it at the end of the task, rather than reusing a shared connection pool. This is because `asyncpg` connections are bound to the event loop that created them, and each Celery task runs inside a fresh `asyncio.run()` call — reusing a pooled connection across tasks would raise "attached to a different loop" errors. The cost is a new engine per task instead of pooled reuse; fine at this scale, worth revisiting if delivery volume grows.

---

## API Reference

### Subscribers

```
POST   /api/v1/subscribers                          Register subscriber → returns api_key (once)
GET    /api/v1/subscribers                          List all subscribers
POST   /api/v1/subscribers/{id}/subscriptions       Register a URL for an event type  [auth: x-api-key]
GET    /api/v1/subscribers/{id}/subscriptions       List subscriber's subscriptions    [auth: x-api-key]
```

### Events

```
POST   /api/v1/events                               Ingest event → 202 Accepted [auth: x-api-key]
GET    /api/v1/events                                List events
GET    /api/v1/events/{id}                           Get single event
```

### Dashboard

```
GET    /api/v1/dashboard/stats                      Delivery stats overview
GET    /api/v1/dashboard/delivery-attempts          List attempts (filter: ?status=)
GET    /api/v1/dashboard/delivery-attempts/{id}     Attempt detail + AI analysis
POST   /api/v1/dashboard/delivery-attempts/{id}/retry   Manual retry
GET    /api/v1/dashboard/dead-letter                Dead-letter queue
GET    /api/v1/dashboard/stream                     SSE stream (real-time updates)
```

---

## Getting Started

### Prerequisites

- Docker + Docker Compose
- A [Groq](https://console.groq.com/) API key (optional — AI analysis degrades gracefully without it)

### Run locally

```sh
# 1. Clone the repo
git clone https://github.com/SahilSonar-04/webhook-delivery-system
cd webhook-delivery-system

# 2. Set environment variables for groq ai analysis 
echo "GROQ_API_KEY=your-groq-key-here" > .env

# 3. Start everything
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Mock subscriber | http://localhost:9000 |

### Run tests

```sh
docker compose exec backend pytest
```

---

## Deployment

The backend, worker, database, and Redis all deploy together via a Render Blueprint (`render.yaml`). The frontend deploys separately to Vercel.

---

## Demo

The frontend includes an interactive `/demo` page that walks through every scenario without manual setup:

| Scenario | What it shows |
|---|---|
| Successful delivery | HMAC-signed payload delivered on the first attempt |
| Failure + retry | 500 response — watch exponential backoff, `next_retry_at` advancing |
| Dead letter + AI | All 5 retries exhausted, Groq classifies the failure |
| Idempotency | Same `idempotency_key` fired twice — second call returns the identical `event_id` |
| No subscription | `queued=0` — event accepted but no matching subscriber |
| Timeout | Subscriber hangs for 60s, worker cuts the connection at 30s and schedules a retry |

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # subscribers, events, dashboard (SSE)
│   │   ├── models/             # SQLAlchemy ORM (Subscriber, Event, DeliveryAttempt, AIFailureAnalysis)
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # subscriber_service, event_service, delivery_service
│   │   ├── workers/
│   │   │   ├── celery_app.py   # Celery config (acks_late, reject_on_worker_lost)
│   │   │   ├── delivery_worker.py  # Core delivery loop — HTTP, retry, signing, pub/sub
│   │   │   └── ai_worker.py    # Groq analysis task
│   │   ├── core/config.py      # Settings via pydantic-settings
│   │   └── main.py             # FastAPI app + CORS + lifespan
│   ├── tests/                  # pytest-asyncio test suite
│   ├── Dockerfile
│   └── start.sh                # Starts Celery worker + uvicorn in one container
├── frontend/
│   ├── app/
│   │   ├── dashboard/          # Overview, Events, Attempts, Dead Letter, Subscribers
│   │   └── demo/               # Interactive scenario runner
│   └── lib/api.ts              # Typed fetch wrapper
├── mock-subscriber/            # FastAPI server — /webhook, /webhook/fail, /webhook/slow
├── docker-compose.yml
└── render.yaml                 # Render deployment config
```

---

## Environment Variables

### Backend

```env
# Local Docker Compose only needs GROQ_API_KEY (see above)
# The rest are hardcoded in docker-compose.yml for local dev.
# This full list is what the backend container receives regardless of
# how it's run — reference it when deploying (e.g. Render env vars).

DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/webhook_db
REDIS_URL=redis://redis:6379/0
GROQ_API_KEY=your-groq-key          # optional
FRONTEND_URL=https://your-frontend  # comma-separated for multiple origins

# Delivery tuning (optional — these are the defaults)
MAX_RETRY_ATTEMPTS=5
BASE_RETRY_DELAY=30
MAX_RETRY_DELAY=7200
DELIVERY_TIMEOUT=30
```

### Frontend (build-time)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000    # or your deployed backend URL
NEXT_PUBLIC_MOCK_URL=http://localhost:9000   # or your deployed mock-subscriber URL
```

---

## License

MIT