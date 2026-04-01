from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AIAnalysisResponse(BaseModel):
    id: UUID
    failure_category: str
    explanation: str
    suggested_fix: str
    confidence_score: float
    severity: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryAttemptResponse(BaseModel):
    id: UUID
    event_id: UUID
    subscription_id: UUID
    status: str
    attempt_number: int
    next_retry_at: Optional[datetime]
    response_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    duration_ms: Optional[float]
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    ai_analysis: Optional[AIAnalysisResponse] = None

    model_config = {"from_attributes": True}


class DeliveryAttemptDetail(DeliveryAttemptResponse):
    event: Optional[dict] = None

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_events: int
    delivered: int
    failed: int
    pending: int
    dead: int
    success_rate: float


class RetryResponse(BaseModel):
    message: str
    delivery_attempt_id: UUID