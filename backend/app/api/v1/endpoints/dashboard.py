from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.delivery_service import delivery_service
from app.schemas.delivery import (
    DeliveryAttemptResponse,
    DashboardStats,
    RetryResponse,
)
from app.workers.delivery_worker import deliver_webhook
import uuid
import json
import asyncio
import logging
import redis.asyncio as aioredis
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Overall delivery statistics."""
    return await delivery_service.get_dashboard_stats(db)


@router.get("/delivery-attempts", response_model=list[DeliveryAttemptResponse])
async def list_delivery_attempts(
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all delivery attempts with optional status filter."""
    return await delivery_service.get_all_delivery_attempts(
        db, status=status, skip=skip, limit=limit
    )


@router.get("/delivery-attempts/{attempt_id}", response_model=DeliveryAttemptResponse)
async def get_delivery_attempt(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    attempt = await delivery_service.get_delivery_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery attempt not found")
    return attempt


@router.post("/delivery-attempts/{attempt_id}/retry", response_model=RetryResponse)
async def retry_delivery(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually retry a failed or dead delivery."""
    attempt = await delivery_service.mark_for_retry(db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery attempt not found")
    # Flush so the status update is visible; get_db commits on response exit.
    # Celery task is queued after flush so the worker sees the updated row.
    await db.flush()
    deliver_webhook.delay(str(attempt.id))
    return RetryResponse(
        message="Retry queued successfully",
        delivery_attempt_id=attempt.id,
    )


@router.get("/dead-letter", response_model=list[DeliveryAttemptResponse])
async def get_dead_letter_queue(db: AsyncSession = Depends(get_db)):
    """All deliveries that exhausted retries."""
    return await delivery_service.get_dead_letter_queue(db)


@router.get("/stream")
async def stream_events(request: Request):
    """
    Server-Sent Events stream.
    Frontend connects here to get real-time delivery updates.
    Cleans up properly when the client disconnects.
    """
    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        try:
            await pubsub.subscribe("webhook_events")
        except Exception as e:
            logger.error(f"SSE: failed to subscribe to Redis: {e}")
            await r.aclose()
            return

        try:
            while True:
                # Check if client disconnected before doing any work
                if await request.is_disconnected():
                    break

                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                except Exception as e:
                    # Redis connection dropped mid-stream. Yield an error event
                    # so the client knows, then stop — the EventSource will
                    # reconnect automatically, avoiding a tight spin-loop.
                    logger.error(f"SSE: Redis pubsub error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'stream interrupted'})}\n\n"
                    break

                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    yield f"data: {data}\n\n"
                else:
                    # Heartbeat keeps the connection alive and lets us detect
                    # a closed socket on the next iteration
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

                await asyncio.sleep(0.5)
        finally:
            try:
                await pubsub.unsubscribe("webhook_events")
                await pubsub.aclose()
            except Exception:
                pass
            try:
                await r.aclose()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )