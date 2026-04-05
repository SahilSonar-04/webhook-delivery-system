import pytest
from httpx import AsyncClient


async def test_create_subscriber(client: AsyncClient):
    response = await client.post("/api/v1/subscribers", json={
        "name": "Test Service",
        "email": "test@example.com"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test Service"
    assert "api_key" in data
    assert data["api_key"].startswith("wh_")
    assert data["is_active"] is True


async def test_create_subscriber_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/subscribers", json={
        "name": "First",
        "email": "dup@example.com"
    })
    response = await client.post("/api/v1/subscribers", json={
        "name": "Second",
        "email": "dup@example.com"
    })
    assert response.status_code == 400


async def test_list_subscribers_empty(client: AsyncClient):
    response = await client.get("/api/v1/subscribers")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_subscribers(client: AsyncClient):
    await client.post("/api/v1/subscribers", json={
        "name": "Alpha", "email": "alpha@example.com"
    })
    await client.post("/api/v1/subscribers", json={
        "name": "Beta", "email": "beta@example.com"
    })
    response = await client.get("/api/v1/subscribers")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_create_subscription(client: AsyncClient):
    # Register subscriber
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Sub1", "email": "sub1@example.com"
    })
    sub_data = sub_resp.json()
    api_key = sub_data["api_key"]
    subscriber_id = sub_data["id"]

    # Create subscription
    response = await client.post(
        f"/api/v1/subscribers/{subscriber_id}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://example.com/hook"},
        headers={"x-api-key": api_key},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "order.created"
    assert data["target_url"] == "http://example.com/hook"


async def test_create_subscription_wrong_api_key(client: AsyncClient):
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Sub2", "email": "sub2@example.com"
    })
    subscriber_id = sub_resp.json()["id"]

    response = await client.post(
        f"/api/v1/subscribers/{subscriber_id}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://example.com/hook"},
        headers={"x-api-key": "wh_wrongkey"},
    )
    assert response.status_code == 401


async def test_list_subscriptions(client: AsyncClient):
    sub_resp = await client.post("/api/v1/subscribers", json={
        "name": "Sub3", "email": "sub3@example.com"
    })
    sub_data = sub_resp.json()
    api_key = sub_data["api_key"]
    subscriber_id = sub_data["id"]

    await client.post(
        f"/api/v1/subscribers/{subscriber_id}/subscriptions",
        json={"event_type": "order.created", "target_url": "http://a.com/hook"},
        headers={"x-api-key": api_key},
    )
    await client.post(
        f"/api/v1/subscribers/{subscriber_id}/subscriptions",
        json={"event_type": "order.shipped", "target_url": "http://b.com/hook"},
        headers={"x-api-key": api_key},
    )

    response = await client.get(
        f"/api/v1/subscribers/{subscriber_id}/subscriptions",
        headers={"x-api-key": api_key},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2