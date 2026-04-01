from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.event_service import event_service
from app.services.subscriber_service import subscriber_service
from app.services.delivery_service import delivery_service
from app.schemas.event import EventCreate, EventResponse
from app.workers.delivery_worker import deliver_webhook
import uuid

router = APIRouter()


@router.post("", status_code=202)
async def ingest_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept an event from a producer.
    Stores it, creates delivery attempts, queues async delivery.
    Returns 202 Accepted immediately — does not wait for delivery.
    """
    # Create or get existing event (idempotency)
    event = await event_service.create_event(db, data)

    # Find all matching subscriptions
    subscriptions = await subscriber_service.get_matching_subscriptions(
        db, data.event_type
    )

    if not subscriptions:
        return {
            "event_id": str(event.id),
            "message": "Event accepted. No active subscriptions found.",
            "queued": 0,
        }

    # Create delivery attempt for each subscription and queue
    queued = 0
    for subscription in subscriptions:
        attempt = await delivery_service.create_delivery_attempt(
            db, event.id, subscription.id
        )
        await db.commit()

        # Queue async delivery task
        deliver_webhook.delay(str(attempt.id))
        queued += 1

    return {
        "event_id": str(event.id),
        "message": "Event accepted and queued for delivery.",
        "queued": queued,
    }


@router.get("", response_model=list[EventResponse])
async def list_events(
    skip: int = 0,
    limit: int = 50,
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