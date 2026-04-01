from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class EventCreate(BaseModel):
    event_type: str
    payload: dict[str, Any]
    producer_id: str
    idempotency_key: str


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    payload: dict[str, Any]
    producer_id: str
    idempotency_key: str
    created_at: datetime

    model_config = {"from_attributes": True}