import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.database import get_db
from app.services.event_service import event_service
from app.services.subscriber_service import subscriber_service
from app.services.delivery_service import delivery_service
from app.schemas.event import EventCreate, EventResponse
from app.workers.delivery_worker import deliver_webhook
from app.core.security import verify_producer_api_key
from app.core.logging import get_logger
from app.models.producer import Producer

router = APIRouter()
logger = get_logger(__name__)


@router.post("", status_code=202)
async def ingest_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    producer: Producer = Depends(verify_producer_api_key),
):
    correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")

    event, was_created = await event_service.create_event(db, data, producer.id)

    if not was_created:
        logger.info(
            "event.duplicate",
            event_id=str(event.id),
            event_type=data.event_type,
            idempotency_key=data.idempotency_key,
        )
        return {
            "event_id": str(event.id),
            "message": "Event already processed for this idempotency_key. No new deliveries queued.",
            "queued": 0,
        }

    subscriptions = await subscriber_service.get_matching_subscriptions(
        db, data.event_type, producer.id
    )

    if not subscriptions:
        await db.commit()
        logger.info(
            "event.no_subscriptions",
            event_id=str(event.id),
            event_type=data.event_type,
        )
        return {
            "event_id": str(event.id),
            "message": "Event accepted. No active subscriptions found.",
            "queued": 0,
        }

    queued = 0
    attempt_ids: list[str] = []
    for subscription in subscriptions:
        attempt = await delivery_service.create_delivery_attempt(
            db, event.id, subscription.id
        )
        attempt_ids.append(str(attempt.id))
        queued += 1

    await db.commit()

    logger.info(
        "event.ingested",
        event_id=str(event.id),
        event_type=data.event_type,
        producer_id=str(producer.id),
        queued=queued,
    )

    for attempt_id in attempt_ids:
        deliver_webhook.delay(attempt_id, correlation_id)

    return {
        "event_id": str(event.id),
        "message": "Event accepted and queued for delivery.",
        "queued": queued,
    }


@router.get("", response_model=list[EventResponse])
async def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await event_service.get_all_events(db, skip=skip, limit=limit)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    event = await event_service.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
