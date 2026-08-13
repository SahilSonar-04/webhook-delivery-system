from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime


class ProducerCreate(BaseModel):
    name: str
    email: EmailStr


class ProducerResponse(BaseModel):
    id: UUID
    name: str
    email: str
    api_key: str  # shown once on creation
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProducerPublic(BaseModel):
    id: UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
    