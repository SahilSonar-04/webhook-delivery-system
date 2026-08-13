import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subscriber_service import subscriber_service
from app.services.producer_service import producer_service
from app.services.event_service import event_service
from app.services.delivery_service import delivery_service
from app.schemas.subscriber import SubscriberCreate, SubscriptionCreate
from app.schemas.producer import ProducerCreate
from app.schemas.event import EventCreate


async def _make_producer(db_session: AsyncSession, email: str):
    return await producer_service.create_producer(
        db_session, ProducerCreate(name="Test Producer", email=email)
    )


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
    assert subscription.producer_id is None


async def test_get_matching_subscriptions(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Eve", email="eve@test.com")
    )
    producer = await _make_producer(db_session, "eve-producer@test.com")
    await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="ping", target_url="http://a.com"),
    )
    await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(event_type="pong", target_url="http://b.com"),
    )
    matches = await subscriber_service.get_matching_subscriptions(
        db_session, "ping", producer.id
    )
    assert len(matches) == 1
    assert matches[0].event_type == "ping"


async def test_get_matching_subscriptions_respects_producer_scope(db_session: AsyncSession):
    sub = await subscriber_service.create_subscriber(
        db_session, SubscriberCreate(name="Frank", email="frank@test.com")
    )
    producer_a = await _make_producer(db_session, "frank-producer-a@test.com")
    producer_b = await _make_producer(db_session, "frank-producer-b@test.com")
    await subscriber_service.create_subscription(
        db_session, sub.id,
        SubscriptionCreate(
            event_type="scoped.event", target_url="http://a.com", producer_id=producer_a.id
        ),
    )
    matches_a = await subscriber_service.get_matching_subscriptions(
        db_session, "scoped.event", producer_a.id
    )
    matches_b = await subscriber_service.get_matching_subscriptions(
        db_session, "scoped.event", producer_b.id
    )
    assert len(matches_a) == 1
    assert len(matches_b) == 0


# ── Producer Service ─────────────────────────────────────────────

async def test_producer_service_create(db_session: AsyncSession):
    producer = await _make_producer(db_session, "gina@test.com")
    assert producer.email == "gina@test.com"
    assert producer.api_key.startswith("pk_")


async def test_producer_service_duplicate_raises(db_session: AsyncSession):
    data = ProducerCreate(name="Henry", email="henry@test.com")
    await producer_service.create_producer(db_session, data)
    with pytest.raises(ValueError, match="already exists"):
        await producer_service.create_producer(db_session, data)


async def test_producer_service_get_by_api_key(db_session: AsyncSession):
    producer = await _make_producer(db_session, "iris@test.com")
    found = await producer_service.get_producer_by_api_key(db_session, producer.api_key)
    assert found is not None
    assert found.id == producer.id


# ── Event Service ───────────────────────────────────────────────

async def test_event_service_create(db_session: AsyncSession):
    producer = await _make_producer(db_session, "event-create@test.com")
    event, was_created = await event_service.create_event(
        db_session,
        EventCreate(
            event_type="order.created",
            payload={"order_id": 1},
            idempotency_key="evt-001",
        ),
        producer.id,
    )
    assert event.event_type == "order.created"
    assert event.idempotency_key == "evt-001"
    assert event.producer_id == producer.id
    assert was_created is True


async def test_event_service_idempotency(db_session: AsyncSession):
    producer = await _make_producer(db_session, "event-idem@test.com")
    data = EventCreate(
        event_type="order.created",
        payload={"x": 1},
        idempotency_key="evt-idem",
    )
    e1, created1 = await event_service.create_event(db_session, data, producer.id)
    e2, created2 = await event_service.create_event(db_session, data, producer.id)
    assert e1.id == e2.id
    assert created1 is True
    assert created2 is False


async def test_event_service_get(db_session: AsyncSession):
    producer = await _make_producer(db_session, "event-get@test.com")
    event, _ = await event_service.create_event(
        db_session,
        EventCreate(
            event_type="test",
            payload={},
            idempotency_key="evt-get",
        ),
        producer.id,
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
    producer = await _make_producer(db_session, "delivery-create-attempt@test.com")
    event, _ = await event_service.create_event(
        db_session,
        EventCreate(event_type="x", payload={}, idempotency_key="da-001"),
        producer.id,
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
    producer = await _make_producer(db_session, "delivery-mark-retry@test.com")
    event, _ = await event_service.create_event(
        db_session,
        EventCreate(event_type="y", payload={}, idempotency_key="retry-001"),
        producer.id,
    )
    attempt = await delivery_service.create_delivery_attempt(
        db_session, event.id, subscription.id
    )
    attempt.status = "failed"
    await db_session.flush()

    updated = await delivery_service.mark_for_retry(db_session, attempt.id)
    assert updated.status == "pending"
    assert updated.attempt_number == 0
    assert updated.next_retry_at is None


async def test_delivery_service_dashboard_stats(db_session: AsyncSession):
    stats = await delivery_service.get_dashboard_stats(db_session)
    assert stats.total_events == 0
    assert stats.success_rate == 0.0
    