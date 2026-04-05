import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, Float, ForeignKey
from sqlalchemy import DateTime as SaDateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=False,
        index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id"),
        nullable=False,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )

    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(SaDateTime(timezone=True), nullable=True)

    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    delivered_at: Mapped[datetime | None] = mapped_column(SaDateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        SaDateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        SaDateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped["Event"] = relationship(back_populates="delivery_attempts")
    subscription: Mapped["Subscription"] = relationship(
        back_populates="delivery_attempts"
    )
    ai_analysis: Mapped["AIFailureAnalysis | None"] = relationship(
        back_populates="delivery_attempt",
        uselist=False
    )


class AIFailureAnalysis(Base):
    __tablename__ = "ai_failure_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    delivery_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_attempts.id"),
        unique=True,
        nullable=False
    )
    failure_category: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        SaDateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    delivery_attempt: Mapped["DeliveryAttempt"] = relationship(
        back_populates="ai_analysis"
    )