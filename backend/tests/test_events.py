import pytest
from httpx import AsyncClient


async def test_ingest_event_no_subscriptions(client: AsyncClient):
    response = await client.post("/api/v1/events", json={
        "event_type": "order.created",
        "payload": {"order_id": 123},
        "producer_id": "shop-service",
        "idempotency_key": "test-key-001"
    })
    assert response.status_code == 202
    data = response.json()
    assert "event_id" in data
    assert data["queued"] == 0
    assert "No active subscriptions" in data["message"]


async def test_ingest_event_idempotency(client: AsyncClient):
    payload = {
        "event_type": "order.created",
        "payload": {"order_id": 456},
        "producer_id": "shop-service",
        "idempotency_key": "unique-key-abc"
    }
    r1 = await client.post("/api/v1/events", json=payload)
    r2 = await client.post("/api/v1/events", json=payload)

    assert r1.status_code == 202
    assert r2.status_code == 202
    # Same event_id returned — idempotent
    assert r1.json()["event_id"] == r2.json()["event_id"]


async def test_ingest_event_queues_for_subscribers(client: AsyncClient):
    # Register a subscriber + subscription first
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Listener", "email": "listener@example.com"
    })
    sub_data = sub_resp.json()
    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://mock/webhook"},
        headers={"x-api-key": sub_data["api_key"]},
    )

    response = await client.post("/api/v1/events", json={
        "event_type": "order.created",
        "payload": {"order_id": 789},
        "producer_id": "shop-service",
        "idempotency_key": "key-queued-001"
    })
    assert response.status_code == 202
    assert response.json()["queued"] == 1


async def test_get_event_by_id(client: AsyncClient):
    resp = await client.post("/api/v1/events", json={
        "event_type": "payment.received",
        "payload": {"amount": 99.99},
        "producer_id": "billing",
        "idempotency_key": "pay-001"
    })
    event_id = resp.json()["event_id"]

    get_resp = await client.get(f"/api/v1/events/{event_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == event_id
    assert data["event_type"] == "payment.received"


async def test_get_event_not_found(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/v1/events/{fake_id}")
    assert response.status_code == 404


async def test_list_events(client: AsyncClient):
    for i in range(3):
        await client.post("/api/v1/events", json={
            "event_type": "ping",
            "payload": {"i": i},
            "producer_id": "test",
            "idempotency_key": f"list-test-{i}"
        })
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    assert len(response.json()) >= 3