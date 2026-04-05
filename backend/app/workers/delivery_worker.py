import uuid
import asyncio
import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.models.delivery import DeliveryAttempt
from app.models.subscriber import Subscription, Subscriber

import httpx
import logging

logger = logging.getLogger(__name__)


def make_session() -> tuple:
    """
    Create a fresh engine + session bound to the current event loop.
    Must be called from inside an async context (inside asyncio.run()).
    Returns (engine, session_factory) — caller must dispose the engine when done.
    """
    engine = create_async_engine(
        settings.async_database_url,
        echo=False,           # reduce noise in worker logs
        pool_size=1,          # single connection per task — no pool reuse issues
        max_overflow=0,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def publish_event(event_type: str, data: dict):
    """Publish delivery status update to Redis Pub/Sub."""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        payload = json.dumps({"type": event_type, "data": data})
        await r.publish("webhook_events", payload)
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")
    finally:
        await r.aclose()


def calculate_retry_delay(attempt_number: int) -> int:
    """
    Exponential backoff with jitter.
    Attempt 1: ~30s, 2: ~60s, 3: ~120s, 4: ~240s, 5: dead
    """
    base = settings.BASE_RETRY_DELAY
    delay = min(base * (2 ** attempt_number), settings.MAX_RETRY_DELAY)
    jitter = random.randint(0, 10)
    return delay + jitter


def sign_payload(payload: str, secret: str) -> str:
    mac = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    )
    return mac.hexdigest()


async def attempt_delivery(attempt_id: str):
    """Core async delivery logic — runs inside a fresh event loop each time."""
    engine, session_factory = make_session()

    try:
        async with session_factory() as db:
            result = await db.execute(
                select(DeliveryAttempt)
                .options(
                    selectinload(DeliveryAttempt.event),
                    selectinload(DeliveryAttempt.subscription)
                    .selectinload(Subscription.subscriber),
                )
                .where(DeliveryAttempt.id == uuid.UUID(attempt_id))
            )
            attempt = result.scalar_one_or_none()

            if not attempt:
                logger.error(f"Delivery attempt {attempt_id} not found")
                return

            event = attempt.event
            subscription = attempt.subscription
            subscriber = subscription.subscriber

            # Snapshot previous failure details before overwriting so history
            # isn't silently lost when the row is updated on this attempt.
            prev_error = attempt.error_message
            prev_response_code = attempt.response_code
            prev_response_body = attempt.response_body

            # Mark as delivering
            attempt.status = "delivering"
            attempt.attempt_number += 1
            await db.commit()

            await publish_event("delivery_started", {
                "attempt_id": attempt_id,
                "event_type": event.event_type,
                "status": "delivering",
                "attempt_number": attempt.attempt_number,
            })

            # Build and sign payload
            payload_dict = {
                "event_id": str(event.id),
                "event_type": event.event_type,
                "payload": event.payload,
                "attempt": attempt.attempt_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            payload_str = json.dumps(payload_dict)
            signature = sign_payload(payload_str, subscriber.secret)

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": f"sha256={signature}",
                "X-Webhook-Event": event.event_type,
                "X-Webhook-Attempt": str(attempt.attempt_number),
            }

            start_time = time.time()
            # Tracks whether we need to enqueue a retry or AI analysis after commit.
            _retry_delay: int | None = None
            _trigger_ai: bool = False

            try:
                async with httpx.AsyncClient(timeout=settings.DELIVERY_TIMEOUT) as client:
                    response = await client.post(
                        subscription.target_url,
                        content=payload_str,
                        headers=headers,
                    )

                # Capture duration once, immediately after the HTTP call completes.
                duration_ms = (time.time() - start_time) * 1000
                attempt.duration_ms = duration_ms
                attempt.response_code = response.status_code
                attempt.response_body = response.text[:500]

                if response.status_code < 300:
                    attempt.status = "delivered"
                    attempt.delivered_at = datetime.now(timezone.utc)
                    logger.info(f"Delivered {attempt_id} → {response.status_code}")

                    await publish_event("delivery_success", {
                        "attempt_id": attempt_id,
                        "event_type": event.event_type,
                        "status": "delivered",
                        "response_code": response.status_code,
                        "duration_ms": duration_ms,
                    })
                else:
                    raise Exception(f"Non-2xx response: {response.status_code}")

            except Exception as e:
                # Only recalculate duration if it wasn't already set above
                # (i.e. the exception came from the HTTP call itself, not from
                # the non-2xx branch which already captured it).
                if attempt.duration_ms is None:
                    attempt.duration_ms = (time.time() - start_time) * 1000

                # Build error message that includes previous attempt context so
                # the audit trail isn't silently overwritten on each retry.
                current_error = str(e)[:400]
                if prev_error and prev_response_code:
                    history_note = f"[prev attempt #{attempt.attempt_number - 1}: {prev_response_code} — {prev_error[:80]}] "
                elif prev_error:
                    history_note = f"[prev attempt #{attempt.attempt_number - 1}: {prev_error[:80]}] "
                else:
                    history_note = ""
                attempt.error_message = (history_note + current_error)[:500]

                if attempt.attempt_number >= settings.MAX_RETRY_ATTEMPTS:
                    attempt.status = "dead"
                    attempt.next_retry_at = None
                    logger.warning(f"Attempt {attempt_id} moved to dead letter queue")

                    await publish_event("delivery_dead", {
                        "attempt_id": attempt_id,
                        "event_type": event.event_type,
                        "status": "dead",
                        "error": str(e)[:200],
                    })

                    # Flag for post-commit dispatch — do NOT call before commit.
                    _trigger_ai = True
                else:
                    # Use attempt_number - 1 so the first retry (attempt 1) uses
                    # delay index 0, matching the docstring: ~30s, ~60s, ~120s …
                    delay = calculate_retry_delay(attempt.attempt_number - 1)
                    _retry_delay = delay
                    attempt.status = "failed"
                    attempt.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    logger.info(f"Retry {attempt.attempt_number} in {delay}s")

                    await publish_event("delivery_failed", {
                        "attempt_id": attempt_id,
                        "event_type": event.event_type,
                        "status": "failed",
                        "attempt_number": attempt.attempt_number,
                        "next_retry_in_seconds": delay,
                        "error": str(e)[:200],
                    })

            # Commit all status changes before dispatching any follow-up tasks
            # so workers never observe a stale/uncommitted row.
            await db.commit()

            if _trigger_ai:
                from app.workers.ai_worker import analyze_failure
                analyze_failure.delay(attempt_id)

            if _retry_delay is not None:
                deliver_webhook.apply_async(
                    args=[attempt_id],
                    countdown=_retry_delay,
                )

    finally:
        # Always dispose the engine so the connection is fully closed
        # before this event loop exits — prevents the "attached to a different loop" error
        await engine.dispose()


@celery_app.task(name="deliver_webhook", bind=True, max_retries=0)
def deliver_webhook(self, attempt_id: str):
    """
    Celery task entry point.
    Each call gets a completely fresh event loop + DB engine, so asyncpg
    never tries to reuse a connection from a previous (closed) loop.
    """
    asyncio.run(attempt_delivery(attempt_id))