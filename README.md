# 🪝 Webhook Delivery System

A production-grade async webhook delivery engine built with **FastAPI**, **Celery**, **PostgreSQL**, **Redis**, and **Next.js** — featuring AI-powered failure analysis via Groq.

---

## Overview

A reliable fan-out system that accepts events from producers, matches them against subscriber registrations, and delivers signed payloads asynchronously with guaranteed retry semantics. Built to survive worker crashes, network failures, and slow endpoints — with a live dashboard to observe everything in real time.

---

## Features

### Delivery Engine
- **Async fan-out** — events accepted instantly (202), delivery happens in the background via Celery
- **Exponential backoff** with jitter — ~30s, ~60s, ~120s, ~240s across 5 attempts
- **Dead-letter queue** — exhausted attempts are quarantined for manual inspection and retry
- **HMAC-SHA256 payload signing** — every request carries `X-Webhook-Signature: sha256=<hex>`
- **Idempotency key deduplication** — duplicate events with the same key are no-ops, not re-delivered
- **TTL-aware retry scheduling** — `next_retry_at` stored per attempt; workers pick up at the right time
- **Zero job loss** — `acks_late` + `reject_on_worker_lost` ensures tasks re-queue on hard crashes
- **Stuck delivery recovery** — deliveries locked in `delivering` state for >2× timeout are reset on startup

### Observability
- **Redis Pub/Sub + SSE** — live event stream pushed to the dashboard without polling
- **DB-polling fallback** — SSE stream auto-recovers if the Redis connection drops mid-session
- **Per-attempt detail** — response code, body, duration, error history, retry schedule
- **Dashboard stats** — total events, attempt breakdown (delivered / failed / pending / dead), success rate

### AI Failure Analysis
- **Groq LLM (Llama 3.1)** classifies every dead-letter attempt automatically
- Returns: `failure_category`, `explanation`, `suggested_fix`, `confidence_score`, `severity`
- Gracefully falls back to a generic analysis if the Groq API is unavailable

### Auth & Security
- **API key authentication** — subscribers receive a `wh_`-prefixed key on registration (shown once)
- **HMAC request signing** — subscribers can verify payload integrity independently
- **Subscriber-scoped subscriptions** — only the key-holder can manage their own subscriptions

### Infrastructure
- **Docker Compose** — one command brings up Postgres, Redis, backend, Celery worker, mock subscriber, and Next.js frontend
- **Render deployment** — `render.yaml` included for zero-config cloud deploy
- **Async SQLAlchemy** — isolated per-request DB sessions, `asyncpg` driver throughout
- **Mock subscriber** — FastAPI server with `/webhook` (success), `/webhook/fail` (500), `/webhook/slow` (60s hang) endpoints for local testing

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
| Deployment | Render |

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
POST   /api/v1/events                               Ingest event → 202 Accepted[auth: x-api-key]
GET    /api/v1/events                               List events
GET    /api/v1/events/{id}                          Get single event
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

# 2. Set environment variables
cp backend/.env.example backend/.env
# Edit backend/.env — add GROQ_API_KEY if you want AI analysis

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

## Demo

The frontend includes a fully interactive `/demo` page that walks through every scenario without any manual setup:

| Scenario | What it shows |
|---|---|
| Successful delivery | Happy path — HMAC-signed payload delivered on first attempt |
| Failure + retry | 500 response, watch exponential backoff with `next_retry_at` advancing |
| Dead letter + AI | All 5 retries exhausted, Groq classifies the failure |
| Idempotency | Same `idempotency_key` fired twice — second call returns identical `event_id` |
| No subscription | `queued=0` — event accepted but no matching subscriber |
| Timeout | Subscriber hangs 60s, worker cuts at 30s and schedules retry |

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
│   │   │   ├── delivery_worker.py  # Core agent loop — HTTP, retry, signing, pub/sub
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

```env
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/webhook_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-key          # optional
FRONTEND_URL=https://your-frontend  # comma-separated for multiple origins

# Delivery tuning (optional — these are the defaults)
MAX_RETRY_ATTEMPTS=5
BASE_RETRY_DELAY=30
MAX_RETRY_DELAY=7200
DELIVERY_TIMEOUT=30
```

---

## License

MIT
