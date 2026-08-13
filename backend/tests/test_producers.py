import pytest
from httpx import AsyncClient


async def test_create_producer(client: AsyncClient):
    response = await client.post("/api/v1/producers", json={
        "name": "Order Service",
        "email": "order-service@example.com"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "order-service@example.com"
    assert data["name"] == "Order Service"
    assert "api_key" in data
    assert data["api_key"].startswith("pk_")
    assert data["is_active"] is True


async def test_create_producer_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/producers", json={
        "name": "First", "email": "dup-producer@example.com"
    })
    response = await client.post("/api/v1/producers", json={
        "name": "Second", "email": "dup-producer@example.com"
    })
    assert response.status_code == 400


async def test_list_producers_empty(client: AsyncClient):
    response = await client.get("/api/v1/producers")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_producers(client: AsyncClient):
    await client.post("/api/v1/producers", json={
        "name": "Alpha Producer", "email": "alpha-producer@example.com"
    })
    await client.post("/api/v1/producers", json={
        "name": "Beta Producer", "email": "beta-producer@example.com"
    })
    response = await client.get("/api/v1/producers")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_ingest_event_rejects_subscriber_key(client: AsyncClient):
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Sub", "email": "not-a-producer@example.com"
    })
    sub_data = sub_resp.json()

    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {},
            "idempotency_key": "cross-key-test-001",
        },
        headers={"x-api-key": sub_data["api_key"]},
    )
    assert response.status_code == 401


async def test_ingest_event_rejects_invalid_producer_key(client: AsyncClient):
    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {},
            "idempotency_key": "cross-key-test-002",
        },
        headers={"x-api-key": "pk_notreal"},
    )
    assert response.status_code == 401


async def test_ingest_event_with_valid_producer_key(client: AsyncClient):
    prod_resp = await client.post("/api/v1/producers", json={
        "name": "Valid Producer", "email": "valid-producer@example.com"
    })
    prod_data = prod_resp.json()

    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "order.created",
            "payload": {"order_id": 1},
            "idempotency_key": "valid-producer-test-001",
        },
        headers={"x-api-key": prod_data["api_key"]},
    )
    assert response.status_code == 202
    assert "event_id" in response.json()


async def test_producer_scoped_subscription(client: AsyncClient):
    prod_a = (await client.post("/api/v1/producers", json={
        "name": "Producer A", "email": "producer-a@example.com"
    })).json()
    prod_b = (await client.post("/api/v1/producers", json={
        "name": "Producer B", "email": "producer-b@example.com"
    })).json()

    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Scoped Sub", "email": "scoped-sub@example.com"
    })
    sub_data = sub_resp.json()

    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={
            "event_type": "payment.created",
            "target_url": "http://mock/hook",
            "producer_id": prod_a["id"],
        },
        headers={"x-api-key": sub_data["api_key"]},
    )

    # Producer B fires the same event_type — should NOT match the
    # producer-A-scoped subscription.
    resp_b = await client.post(
        "/api/v1/events",
        json={
            "event_type": "payment.created",
            "payload": {},
            "idempotency_key": "scoped-test-from-b",
        },
        headers={"x-api-key": prod_b["api_key"]},
    )
    assert resp_b.json()["queued"] == 0

    # Producer A fires it — should match.
    resp_a = await client.post(
        "/api/v1/events",
        json={
            "event_type": "payment.created",
            "payload": {},
            "idempotency_key": "scoped-test-from-a",
        },
        headers={"x-api-key": prod_a["api_key"]},
    )
    assert resp_a.json()["queued"] == 1


async def test_unscoped_subscription_receives_from_any_producer(client: AsyncClient):
    prod_a = (await client.post("/api/v1/producers", json={
        "name": "Any Producer A", "email": "any-producer-a@example.com"
    })).json()
    prod_b = (await client.post("/api/v1/producers", json={
        "name": "Any Producer B", "email": "any-producer-b@example.com"
    })).json()

    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Unscoped Sub", "email": "unscoped-sub@example.com"
    })
    sub_data = sub_resp.json()

    # No producer_id -> accepts from any producer.
    await client.post(
        f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
        json={"event_type": "shipment.dispatched", "target_url": "http://mock/hook"},
        headers={"x-api-key": sub_data["api_key"]},
    )

    for prod in (prod_a, prod_b):
        resp = await client.post(
            "/api/v1/events",
            json={
                "event_type": "shipment.dispatched",
                "payload": {},
                "idempotency_key": f"unscoped-test-{prod['id']}",
            },
            headers={"x-api-key": prod["api_key"]},
        )
        assert resp.json()["queued"] == 1
