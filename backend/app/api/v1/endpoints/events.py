from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.event_service import event_service
from app.services.subscriber_service import subscriber_service
from app.services.delivery_service import delivery_service
from app.schemas.event import EventCreate, EventResponse
from app.workers.delivery_worker import deliver_webhook
from app.core.security import verify_api_key
from app.models.subscriber import Subscriber
import uuid

router = APIRouter()


@router.post("", status_code=202)
async def ingest_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    producer: Subscriber = Depends(verify_api_key),
):
    """
    Accept an event from a producer.
    Requires a valid x-api-key from a registered subscriber.
    Stores the event, creates delivery attempts, queues async delivery.
    Returns 202 Accepted immediately — does not wait for delivery.

    If idempotency_key has already been seen, no new delivery attempts
    are created and no new Celery tasks are queued — the original
    deliveries stand.
    """
    already_seen = await event_service.get_event_by_idempotency_key(
        db, data.idempotency_key
    )
    event = await event_service.create_event(db, data)

    if already_seen:
        return {
            "event_id": str(event.id),
            "message": "Event already processed for this idempotency_key. No new deliveries queued.",
            "queued": 0,
        }

    subscriptions = await subscriber_service.get_matching_subscriptions(
        db, data.event_type
    )

    if not subscriptions:
        await db.commit()
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

    for attempt_id in attempt_ids:
        deliver_webhook.delay(attempt_id)

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