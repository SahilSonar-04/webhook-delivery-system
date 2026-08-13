import uuid
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.producer import Producer
from app.schemas.producer import ProducerCreate


def generate_api_key() -> str:
    return f"pk_{secrets.token_urlsafe(32)}"


class ProducerService:

    async def create_producer(
        self, db: AsyncSession, data: ProducerCreate
    ) -> Producer:
        result = await db.execute(
            select(Producer).where(Producer.email == data.email)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Producer with email {data.email} already exists")

        producer = Producer(
            id=uuid.uuid4(),
            name=data.name,
            email=data.email,
            api_key=generate_api_key(),
        )
        db.add(producer)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Producer with email {data.email} already exists")
        return producer

    async def get_producer_by_api_key(
        self, db: AsyncSession, api_key: str
    ) -> Producer | None:
        result = await db.execute(
            select(Producer).where(
                Producer.api_key == api_key,
                Producer.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_all_producers(
        self, db: AsyncSession
    ) -> list[Producer]:
        result = await db.execute(
            select(Producer).order_by(Producer.created_at.desc())
        )
        return list(result.scalars().all())


producer_service = ProducerService()
