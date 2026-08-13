import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean
from sqlalchemy import DateTime as SaDateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class Producer(Base):
    __tablename__ = "producers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        SaDateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    events: Mapped[list["Event"]] = relationship(back_populates="producer")
    