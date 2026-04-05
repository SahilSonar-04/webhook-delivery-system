import pytest
from httpx import AsyncClient
from unittest.mock import patch


async def test_dashboard_stats_empty(client: AsyncClient):
    response = await client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_events"] == 0
    assert data["total_attempts"] == 0
    assert data["delivered"] == 0
    assert data["failed"] == 0
    assert data["pending"] == 0
    assert data["dead"] == 0
    assert data["success_rate"] == 0.0


async def test_dashboard_stats_after_events(client: AsyncClient):
    with patch("app.api.v1.endpoints.events.deliver_webhook") as mock_task:
        mock_task.delay = lambda *a, **kw: None

        # Create subscriber + subscription
        sub_resp = await client.post("/api/v1/subscribers", json={
            "name": "Stats Test", "email": "stats@test.com"
        })
        sub_data = sub_resp.json()
        await client.post(
            f"/api/v1/subscribers/{sub_data['id']}/subscriptions",
            json={"event_type": "test.event", "target_url": "http://mock/hook"},
            headers={"x-api-key": sub_data["api_key"]},
        )

        # Ingest 2 events
        for i in range(2):
            await client.post("/api/v1/events", json={
                "event_type": "test.event",
                "payload": {},
                "producer_id": "p",
                "idempotency_key": f"stats-key-{i}"
            })

    stats = (await client.get("/api/v1/dashboard/stats")).json()
    assert stats["total_events"] == 2
    assert stats["total_attempts"] == 2
    assert stats["pending"] == 2