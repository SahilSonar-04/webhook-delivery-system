import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import uuid

from app.workers.delivery_worker import calculate_retry_delay, sign_payload


# These are already covered in test_worker_logic.py
# This file focuses on the attempt_delivery logic paths

async def test_attempt_delivery_success(db_session, engine):
    """Test successful HTTP delivery updates status to delivered."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from app.services.subscriber_service import subscriber_service
    from app.services.event_service import event_service
    from app.services.delivery_service import delivery_service
    from app.schemas.subscriber import SubscriberCreate, SubscriptionCreate
    from app.schemas.event import EventCreate
    from app.workers.delivery_worker import attempt_delivery

    # Set up data
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="H", email="h@test.com")
    )
    subscription = await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="ship", target_url="http://mock/hook"),
    )
    event = await event_service.create_event(
        db_session,
        EventCreate(event_type="ship", payload={}, producer_id="p", idempotency_key="adv-001"),
    )
    attempt = await delivery_service.create_delivery_attempt(
        db_session, event.id, subscription.id
    )
    await db_session.commit()

    # Mock the HTTP call to return 200
    import httpx

    async def mock_post(*args, **kwargs):
        return httpx.Response(200, text="ok")

    with patch("app.workers.delivery_worker.make_session") as mock_make_session, \
         patch("app.workers.delivery_worker.publish_event", new_callable=AsyncMock), \
         patch("httpx.AsyncClient.post", new=mock_post):

        mock_make_session.return_value = (engine, async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        ))
        await attempt_delivery(str(attempt.id))

    # Verify status updated
    from sqlalchemy import select
    from app.models.delivery import DeliveryAttempt
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        result = await s.execute(
            select(DeliveryAttempt).where(DeliveryAttempt.id == attempt.id)
        )
        updated = result.scalar_one()
        assert updated.status == "delivered"
        assert updated.delivered_at is not None
        assert updated.response_code == 200


async def test_attempt_delivery_failure_schedules_retry(db_session, engine):
    """Test failed HTTP delivery sets status to failed with retry time."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from app.services.subscriber_service import subscriber_service
    from app.services.event_service import event_service
    from app.services.delivery_service import delivery_service
    from app.schemas.subscriber import SubscriberCreate, SubscriptionCreate
    from app.schemas.event import EventCreate
    from app.workers.delivery_worker import attempt_delivery
    import httpx

    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="I", email="i@test.com")
    )
    subscription = await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="fail.test", target_url="http://mock/fail"),
    )
    event = await event_service.create_event(
        db_session,
        EventCreate(event_type="fail.test", payload={}, producer_id="p", idempotency_key="adv-002"),
    )
    attempt = await delivery_service.create_delivery_attempt(
        db_session, event.id, subscription.id
    )
    await db_session.commit()

    async def mock_post_500(*args, **kwargs):
        return httpx.Response(500, text="error")

    with patch("app.workers.delivery_worker.make_session") as mock_make_session, \
         patch("app.workers.delivery_worker.publish_event", new_callable=AsyncMock), \
         patch("app.workers.delivery_worker.deliver_webhook") as mock_retry, \
         patch("httpx.AsyncClient.post", new=mock_post_500):

        mock_retry.apply_async = MagicMock()
        mock_make_session.return_value = (engine, async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        ))
        await attempt_delivery(str(attempt.id))

    from sqlalchemy import select
    from app.models.delivery import DeliveryAttempt
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        result = await s.execute(
            select(DeliveryAttempt).where(DeliveryAttempt.id == attempt.id)
        )
        updated = result.scalar_one()
        assert updated.status == "failed"
        assert updated.next_retry_at is not None
        assert updated.response_code == 500