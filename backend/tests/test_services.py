import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subscriber_service import subscriber_service
from app.services.event_service import event_service
from app.services.delivery_service import delivery_service
from app.schemas.subscriber import SubscriberCreate, SubscriptionCreate
from app.schemas.event import EventCreate


# ── Subscriber Service ──────────────────────────────────────────

async def test_subscriber_service_create(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Alice", email="alice@test.com")
    )
    assert sub.name == "Alice"
    assert sub.api_key.startswith("wh_")
    assert sub.secret is not None


async def test_subscriber_service_duplicate_raises(db_session: AsyncSession):
    data = SubscriberCreate(name="Bob", email="bob@test.com")
    await subscriber_service.create_subscriber(db_session, data)
    with pytest.raises(ValueError, match="already exists"):
        await subscriber_service.create_subscriber(db_session, data)


async def test_subscriber_service_get_by_api_key(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Carol", email="carol@test.com")
    )
    found = await subscriber_service.get_subscriber_by_api_key(db_session, sub.api_key)
    assert found is not None
    assert found.id == sub.id


async def test_subscriber_service_unknown_api_key(db_session: AsyncSession):
    found = await subscriber_service.get_subscriber_by_api_key(db_session, "wh_doesnotexist")
    assert found is None


async def test_subscription_creation(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Dave", email="dave@test.com")
    )
    subscription = await subscriber_service.create_subscription(
        db_session,
        sub.id,
        SubscriptionCreate(event_type="invoice.paid", target_url="http://x.com/hook"),
    )
    assert subscription.event_type == "invoice.paid"
    assert subscription.subscriber_id == sub.id


async def test_get_matching_subscriptions(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Eve", email="eve@test.com")
    )
    await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="ping", target_url="http://a.com"),
    )
    await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="pong", target_url="http://b.com"),
    )
    matches = await subscriber_service.get_matching_subscriptions(db_session, "ping")
    assert len(matches) == 1
    assert matches[0].event_type == "ping"


# ── Event Service ───────────────────────────────────────────────

async def test_event_service_create(db_session: AsyncSession):
    event = await event_service.create_event(
        db_session,
        EventCreate(
            event_type="order.created",
            payload={"order_id": 1},
            producer_id="shop",
            idempotency_key="evt-001",
        ),
    )
    assert event.event_type == "order.created"
    assert event.idempotency_key == "evt-001"


async def test_event_service_idempotency(db_session: AsyncSession):
    data = EventCreate(
        event_type="order.created",
        payload={"x": 1},
        producer_id="shop",
        idempotency_key="evt-idem",
    )
    e1 = await event_service.create_event(db_session, data)
    e2 = await event_service.create_event(db_session, data)
    assert e1.id == e2.id


async def test_event_service_get(db_session: AsyncSession):
    event = await event_service.create_event(
        db_session,
        EventCreate(
            event_type="test",
            payload={},
            producer_id="p",
            idempotency_key="evt-get",
        ),
    )
    found = await event_service.get_event(db_session, event.id)
    assert found is not None
    assert found.id == event.id


async def test_event_service_get_missing(db_session: AsyncSession):
    result = await event_service.get_event(db_session, uuid.uuid4())
    assert result is None


# ── Delivery Service ────────────────────────────────────────────

async def test_delivery_service_create_attempt(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="F", email="f@test.com")
    )
    subscription = await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="x", target_url="http://x.com"),
    )
    event = await event_service.create_event(
        db_session,
        EventCreate(event_type="x", payload={}, producer_id="p", idempotency_key="da-001"),
    )
    attempt = await delivery_service.create_delivery_attempt(
        db_session, event.id, subscription.id
    )
    assert attempt.status == "pending"
    assert attempt.attempt_number == 0


async def test_delivery_service_mark_for_retry(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="G", email="g@test.com")
    )
    subscription = await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="y", target_url="http://y.com"),
    )
    event = await event_service.create_event(
        db_session,
        EventCreate(event_type="y", payload={}, producer_id="p", idempotency_key="retry-001"),
    )
    attempt = await delivery_service.create_delivery_attempt(
        db_session, event.id, subscription.id
    )
    updated = await delivery_service.mark_for_retry(db_session, attempt.id)
    assert updated.status == "pending"
    assert updated.next_retry_at is None


async def test_delivery_service_dashboard_stats(db_session: AsyncSession):
    stats = await delivery_service.get_dashboard_stats(db_session)
    assert stats.total_events == 0
    assert stats.success_rate == 0.0