import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.event import Event
from app.models.delivery import DeliveryAttempt
from app.schemas.event import EventCreate


class EventService:

    async def create_event(
        self, db: AsyncSession, data: EventCreate
    ) -> Event:
        # Idempotency check — if same key seen before, return existing event
        result = await db.execute(
            select(Event).where(
                Event.idempotency_key == data.idempotency_key
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        event = Event(
            id=uuid.uuid4(),
            event_type=data.event_type,
            payload=data.payload,
            producer_id=data.producer_id,
            idempotency_key=data.idempotency_key,
        )
        db.add(event)
        await db.flush()
        return event

    async def get_event(
        self, db: AsyncSession, event_id: uuid.UUID
    ) -> Event | None:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_all_events(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Event]:
        result = await db.execute(
            select(Event)
            .order_by(Event.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


event_service = EventService()