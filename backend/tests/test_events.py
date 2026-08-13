import pytest
from httpx import AsyncClient


async def _register_producer(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/api/v1/producers", json={
        "name": "Producer", "email": email
    })
    return resp.json()


async def test_ingest_event_no_subscriptions(client: AsyncClient):
    producer = await _register_producer(client, "producer1@test.com")
    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {"order_id": 123},
            "idempotency_key": "test-key-001"
        },
        headers={"x-api-key": producer["api_key"]},
    )
    assert response.status_code == 202
    data = response.json()
    assert "event_id" in data
    assert data["queued"] == 0
    assert "No active subscriptions" in data["message"]


async def test_ingest_event_requires_api_key(client: AsyncClient):
    response = await client.post("/api/v1/events", json={
        "event_type": "order.created",
        "payload": {"order_id": 123},
        "idempotency_key": "test-key-noauth"
    })
    assert response.status_code == 422


async def test_ingest_event_rejects_invalid_api_key(client: AsyncClient):
    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {"order_id": 123},
            "idempotency_key": "test-key-badauth"
        },
        headers={"x-api-key": "pk_notreal"},
    )
    assert response.status_code == 401


async def test_ingest_event_rejects_subscriber_key(client: AsyncClient):
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Not A Producer", "email": "not-a-producer-events-test@test.com"
    })
    sub_data = sub_resp.json()
    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {"order_id": 123},
            "idempotency_key": "test-key-wrongkeytype"
        },
        headers={"x-api-key": sub_data["api_key"]},
    )
    assert response.status_code == 401


async def test_ingest_event_idempotency(client: AsyncClient):
    producer = await _register_producer(client, "producer2@test.com")
    payload = {
        "event_type": "order.created",
        "payload": {"order_id": 456},
        "idempotency_key": "unique-key-abc"
    }
    headers = {"x-api-key": producer["api_key"]}
    r1 = await client.post("/api/v1/events", json=payload, headers=headers)
    r2 = await client.post("/api/v1/events", json=payload, headers=headers)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["event_id"] == r2.json()["event_id"]


async def test_ingest_event_idempotency_does_not_requeue(client: AsyncClient):
    producer = await _register_producer(client, "producer-idem@test.com")
    headers = {"x-api-key": producer["api_key"]}

    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "IdemSub", "email": "idem@example.com"
    })
    sub_data = sub_resp.json()
    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://mock/hook"},
        headers={"x-api-key": sub_data["api_key"]},
    )

    payload = {
        "event_type": "order.created",
        "payload": {"order_id": 1},
        "idempotency_key": "idem-requeue-001"
    }
    r1 = await client.post("/api/v1/events", json=payload, headers=headers)
    r2 = await client.post("/api/v1/events", json=payload, headers=headers)

    assert r1.json()["queued"] == 1
    assert r2.json()["queued"] == 0

    attempts = (await client.get("/api/v1/dashboard/delivery-attempts")).json()
    assert len(attempts) == 1


async def test_ingest_event_queues_for_subscribers(client: AsyncClient):
    producer = await _register_producer(client, "producer3@test.com")

    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Listener", "email": "listener@example.com"
    })
    sub_data = sub_resp.json()
    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://mock/webhook"},
        headers={"x-api-key": sub_data["api_key"]},
    )

    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {"order_id": 789},
            "idempotency_key": "key-queued-001"
        },
        headers={"x-api-key": producer["api_key"]},
    )
    assert response.status_code == 202
    assert response.json()["queued"] == 1


async def test_get_event_by_id(client: AsyncClient):
    producer = await _register_producer(client, "producer4@test.com")
    resp = await client.post(
        "/api/v1/events",
        json={
            "event_type": "payment.received",
            "payload": {"amount": 99.99},
            "idempotency_key": "pay-001"
        },
        headers={"x-api-key": producer["api_key"]},
    )
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
    producer = await _register_producer(client, "producer5@test.com")
    headers = {"x-api-key": producer["api_key"]}
    for i in range(3):
        await client.post(
            "/api/v1/events",
            json={
                "event_type": "ping",
                "payload": {"i": i},
                "idempotency_key": f"list-test-{i}"
            },
            headers=headers,
        )
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    assert len(response.json()) >= 3


async def test_list_events_limit_capped(client: AsyncClient):
    response = await client.get("/api/v1/events?limit=999999")
    assert response.status_code == 422
