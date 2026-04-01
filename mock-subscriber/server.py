from fastapi import FastAPI, Request
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
    """Always returns 500 — for testing retry logic"""
    return {"error": "simulated failure"}, 500

@app.get("/health")
async def health():
    return {"status": "ok"}
