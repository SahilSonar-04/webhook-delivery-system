import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.event import Event
from app.schemas.event import EventCreate


class EventService:

    async def get_event_by_idempotency_key(
        self, db: AsyncSession, idempotency_key: str
    ) -> Event | None:
        result = await db.execute(
            select(Event).where(
                Event.idempotency_key == idempotency_key
            )
        )
        return result.scalar_one_or_none()

    async def create_event(
        self, db: AsyncSession, data: EventCreate, producer_id: uuid.UUID
    ) -> tuple[Event, bool]:
        existing = await self.get_event_by_idempotency_key(db, data.idempotency_key)
        if existing:
            return existing, False

        event = Event(
            id=uuid.uuid4(),
            event_type=data.event_type,
            payload=data.payload,
            producer_id=producer_id,
            idempotency_key=data.idempotency_key,
        )
        db.add(event)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            existing = await self.get_event_by_idempotency_key(db, data.idempotency_key)
            if existing:
                return existing, False
            raise
        return event, True

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
