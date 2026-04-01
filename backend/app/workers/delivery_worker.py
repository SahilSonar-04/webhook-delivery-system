import uuid
import asyncio
import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timedelta
from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.models.delivery import DeliveryAttempt
from app.models.event import Event
from app.models.subscriber import Subscription, Subscriber
from app.db.database import AsyncSessionLocal

import httpx
import logging

logger = logging.getLogger(__name__)


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
    """
    HMAC-SHA256 signature so subscribers can verify
    the request genuinely came from us.
    """
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()


async def attempt_delivery(attempt_id: str):
    """Core async delivery logic."""
    async with AsyncSessionLocal() as db:
        # Load attempt with all related data
        result = await db.execute(
            select(DeliveryAttempt)
            .options(
                selectinload(DeliveryAttempt.event),
                selectinload(DeliveryAttempt.subscription)
                .selectinload(Subscription.subscriber)
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

        # Mark as delivering
        attempt.status = "delivering"
        attempt.attempt_number += 1
        await db.commit()

        # Build payload
        payload_dict = {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "payload": event.payload,
            "attempt": attempt.attempt_number,
            "timestamp": datetime.utcnow().isoformat(),
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

        try:
            async with httpx.AsyncClient(timeout=settings.DELIVERY_TIMEOUT) as client:
                response = await client.post(
                    subscription.target_url,
                    content=payload_str,
                    headers=headers,
                )

            duration_ms = (time.time() - start_time) * 1000
            attempt.duration_ms = duration_ms
            attempt.response_code = response.status_code
            attempt.response_body = response.text[:500]  # store first 500 chars

            if response.status_code < 300:
                # Success
                attempt.status = "delivered"
                attempt.delivered_at = datetime.utcnow()
                logger.info(f"Delivered {attempt_id} → {response.status_code}")
            else:
                # Non-2xx response = failure
                raise Exception(f"Non-2xx response: {response.status_code}")

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            attempt.duration_ms = duration_ms
            attempt.error_message = str(e)[:500]

            if attempt.attempt_number >= settings.MAX_RETRY_ATTEMPTS:
                # All retries exhausted — move to dead letter queue
                attempt.status = "dead"
                attempt.next_retry_at = None
                logger.warning(f"Attempt {attempt_id} moved to dead letter queue")

                # Trigger AI analysis
                from app.workers.ai_worker import analyze_failure
                analyze_failure.delay(attempt_id)
            else:
                # Schedule retry
                delay = calculate_retry_delay(attempt.attempt_number)
                attempt.status = "failed"
                attempt.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                logger.info(f"Retry {attempt.attempt_number} in {delay}s")

                # Requeue with delay
                deliver_webhook.apply_async(
                    args=[attempt_id],
                    countdown=delay,
                )

        await db.commit()


@celery_app.task(name="deliver_webhook", bind=True, max_retries=0)
def deliver_webhook(self, attempt_id: str):
    """
    Celery task — entry point.
    Celery is sync, so we run our async logic in an event loop.
    """
    asyncio.run(attempt_delivery(attempt_id))