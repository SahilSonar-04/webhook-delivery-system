import pytest
import uuid
from httpx import AsyncClient
from unittest.mock import patch


async def _create_subscriber_with_subscription(client, email, event_type, target_url):
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Test", "email": email
    })
    sub_data = sub_resp.json()
    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={"event_type": event_type, "target_url": target_url},
        headers={"x-api-key": sub_data["api_key"]},
    )
    return sub_data


async def _register_producer(client, email) -> dict:
    resp = await client.post("/api/v1/producers", json={
        "name": "Test Producer", "email": email
    })
    return resp.json()


async def _ingest_event(client, api_key, event_type, idempotency_key):
    return await client.post(
        "/api/v1/events",
        json={
            "event_type": event_type,
            "payload": {"test": True},
            "idempotency_key": idempotency_key,
        },
        headers={"x-api-key": api_key},
    )


async def test_list_delivery_attempts_empty(client: AsyncClient):
    response = await client.get("/api/v1/dashboard/delivery-attempts")
    assert response.status_code == 200
    assert response.json() == []


async def test_delivery_attempt_created_on_event(client: AsyncClient):
    with patch("app.api.v1.endpoints.events.deliver_webhook") as mock_task:
        mock_task.delay = lambda *a, **kw: None

        await _create_subscriber_with_subscription(
            client, "d1@test.com", "user.signup", "http://mock/hook"
        )
        producer = await _register_producer(client, "d1-producer@test.com")
        await _ingest_event(client, producer["api_key"], "user.signup", "delivery-test-001")

    response = await client.get("/api/v1/dashboard/delivery-attempts")
    assert response.status_code == 200
    attempts = response.json()
    assert len(attempts) == 1
    assert attempts[0]["status"] == "pending"


async def test_get_delivery_attempt_by_id(client: AsyncClient):
    with patch("app.api.v1.endpoints.events.deliver_webhook") as mock_task:
        mock_task.delay = lambda *a, **kw: None

        await _create_subscriber_with_subscription(
            client, "d2@test.com", "user.signup", "http://mock/hook"
        )
        producer = await _register_producer(client, "d2-producer@test.com")
        await _ingest_event(client, producer["api_key"], "user.signup", "delivery-test-002")

    attempts = (await client.get("/api/v1/dashboard/delivery-attempts")).json()
    attempt_id = attempts[0]["id"]

    response = await client.get(f"/api/v1/dashboard/delivery-attempts/{attempt_id}")
    assert response.status_code == 200
    assert response.json()["id"] == attempt_id


async def test_get_delivery_attempt_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/dashboard/delivery-attempts/{fake_id}")
    assert response.status_code == 404


async def test_filter_attempts_by_status(client: AsyncClient):
    with patch("app.api.v1.endpoints.events.deliver_webhook") as mock_task:
        mock_task.delay = lambda *a, **kw: None

        await _create_subscriber_with_subscription(
            client, "d3@test.com", "order.paid", "http://mock/hook"
        )
        producer = await _register_producer(client, "d3-producer@test.com")
        await _ingest_event(client, producer["api_key"], "order.paid", "delivery-test-003")

    pending = (await client.get("/api/v1/dashboard/delivery-attempts?status=pending")).json()
    delivered = (await client.get("/api/v1/dashboard/delivery-attempts?status=delivered")).json()

    assert len(pending) >= 1
    assert len(delivered) == 0


async def test_dead_letter_queue_empty(client: AsyncClient):
    response = await client.get("/api/v1/dashboard/dead-letter")
    assert response.status_code == 200
    assert response.json() == []


async def test_retry_delivery_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/dashboard/delivery-attempts/{fake_id}/retry", json={}
    )
    assert response.status_code == 404
    