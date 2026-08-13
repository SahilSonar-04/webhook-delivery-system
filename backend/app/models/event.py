import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey
from sqlalchemy import DateTime as SaDateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    producer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("producers.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        SaDateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    producer: Mapped["Producer"] = relationship(back_populates="events")
    delivery_attempts: Mapped[list["DeliveryAttempt"]] = relationship(
        back_populates="event"
    )
