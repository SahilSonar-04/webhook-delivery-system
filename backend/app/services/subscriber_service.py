import uuid
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.subscriber import Subscriber, Subscription
from app.schemas.subscriber import SubscriberCreate, SubscriptionCreate


def generate_api_key() -> str:
    return f"wh_{secrets.token_urlsafe(32)}"


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


class SubscriberService:

    async def create_subscriber(
        self, db: AsyncSession, data: SubscriberCreate
    ) -> Subscriber:
        # Check if email already exists
        result = await db.execute(
            select(Subscriber).where(Subscriber.email == data.email)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Subscriber with email {data.email} already exists")

        subscriber = Subscriber(
            id=uuid.uuid4(),
            name=data.name,
            email=data.email,
            api_key=generate_api_key(),
            secret=generate_secret(),
        )
        db.add(subscriber)
        await db.flush()
        return subscriber

    async def get_subscriber_by_api_key(
        self, db: AsyncSession, api_key: str
    ) -> Subscriber | None:
        result = await db.execute(
            select(Subscriber).where(
                Subscriber.api_key == api_key,
                Subscriber.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_all_subscribers(
        self, db: AsyncSession
    ) -> list[Subscriber]:
        result = await db.execute(
            select(Subscriber).order_by(Subscriber.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_subscription(
        self,
        db: AsyncSession,
        subscriber_id: uuid.UUID,
        data: SubscriptionCreate
    ) -> Subscription:
        subscription = Subscription(
            id=uuid.uuid4(),
            subscriber_id=subscriber_id,
            event_type=data.event_type,
            target_url=data.target_url,
        )
        db.add(subscription)
        await db.flush()
        return subscription

    async def get_subscriptions(
        self, db: AsyncSession, subscriber_id: uuid.UUID
    ) -> list[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                Subscription.subscriber_id == subscriber_id,
                Subscription.is_active == True
            )
        )
        return list(result.scalars().all())

    async def get_matching_subscriptions(
        self, db: AsyncSession, event_type: str
    ) -> list[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                Subscription.event_type == event_type,
                Subscription.is_active == True
            )
        )
        return list(result.scalars().all())


subscriber_service = SubscriberService()