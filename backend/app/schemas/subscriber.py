from pydantic import BaseModel, EmailStr, HttpUrl
from uuid import UUID
from datetime import datetime


# --- Subscriber Schemas ---

class SubscriberCreate(BaseModel):
    name: str
    email: EmailStr


class SubscriberResponse(BaseModel):
    id: UUID
    name: str
    email: str
    api_key: str  # shown once on creation
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriberPublic(BaseModel):
    id: UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Subscription Schemas ---

class SubscriptionCreate(BaseModel):
    event_type: str
    target_url: str


class SubscriptionResponse(BaseModel):
    id: UUID
    subscriber_id: UUID
    event_type: str
    target_url: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}