from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Webhook Subscriber")


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    headers = dict(request.headers)
    logger.info(f"Received webhook: {json.dumps(body, indent=2)}")
    logger.info(f"Signature: {headers.get('x-webhook-signature', 'none')}")
    return {"status": "received", "event_type": body.get("event_type")}


@app.post("/webhook/fail")
async def fail_webhook(request: Request):
    """Always returns 500 — for testing retry logic."""
    body = await request.json()
    logger.info(f"Simulating failure for event: {body.get('event_type')}")
    return JSONResponse(
        status_code=500,
        content={"error": "simulated failure"},
    )


@app.post("/webhook/slow")
async def slow_webhook(request: Request):
    """Simulates a slow endpoint that will trigger timeout — for testing."""
    import asyncio
    await asyncio.sleep(60)
    return {"status": "too late"}


@app.get("/health")
async def health():
    return {"status": "ok"}