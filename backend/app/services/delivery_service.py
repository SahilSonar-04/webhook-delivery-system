import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.delivery import DeliveryAttempt, AIFailureAnalysis
from app.schemas.delivery import DashboardStats


class DeliveryService:

    async def create_delivery_attempt(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
        subscription_id: uuid.UUID,
    ) -> DeliveryAttempt:
        attempt = DeliveryAttempt(
            id=uuid.uuid4(),
            event_id=event_id,
            subscription_id=subscription_id,
            status="pending",
            attempt_number=0,
        )
        db.add(attempt)
        await db.flush()
        return attempt

    async def get_delivery_attempt(
        self, db: AsyncSession, attempt_id: uuid.UUID
    ) -> DeliveryAttempt | None:
        result = await db.execute(
            select(DeliveryAttempt)
            .options(
                selectinload(DeliveryAttempt.ai_analysis),
                selectinload(DeliveryAttempt.event),
                selectinload(DeliveryAttempt.subscription),
            )
            .where(DeliveryAttempt.id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def get_all_delivery_attempts(
        self,
        db: AsyncSession,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[DeliveryAttempt]:
        query = (
            select(DeliveryAttempt)
            .options(
                selectinload(DeliveryAttempt.ai_analysis),
                selectinload(DeliveryAttempt.event),
            )
            .order_by(DeliveryAttempt.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            query = query.where(DeliveryAttempt.status == status)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_dead_letter_queue(
        self, db: AsyncSession
    ) -> list[DeliveryAttempt]:
        result = await db.execute(
            select(DeliveryAttempt)
            .options(
                selectinload(DeliveryAttempt.ai_analysis),
                selectinload(DeliveryAttempt.event),
            )
            .where(DeliveryAttempt.status == "dead")
            .order_by(DeliveryAttempt.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_dashboard_stats(
        self, db: AsyncSession
    ) -> DashboardStats:
        result = await db.execute(
            select(
                func.count(DeliveryAttempt.id).label("total"),
                func.sum(
                    func.cast(DeliveryAttempt.status == "delivered", func.Integer)
                ).label("delivered"),
                func.sum(
                    func.cast(DeliveryAttempt.status == "failed", func.Integer)
                ).label("failed"),
                func.sum(
                    func.cast(DeliveryAttempt.status == "pending", func.Integer)
                ).label("pending"),
                func.sum(
                    func.cast(DeliveryAttempt.status == "dead", func.Integer)
                ).label("dead"),
            )
        )
        row = result.one()
        total = row.total or 0
        delivered = row.delivered or 0

        return DashboardStats(
            total_events=total,
            delivered=delivered,
            failed=row.failed or 0,
            pending=row.pending or 0,
            dead=row.dead or 0,
            success_rate=round((delivered / total * 100), 2) if total > 0 else 0.0,
        )

    async def mark_for_retry(
        self,
        db: AsyncSession,
        attempt_id: uuid.UUID,
    ) -> DeliveryAttempt | None:
        attempt = await self.get_delivery_attempt(db, attempt_id)
        if not attempt:
            return None
        attempt.status = "pending"
        attempt.attempt_number = 0
        attempt.next_retry_at = None
        attempt.error_message = None
        attempt.response_code = None
        await db.flush()
        return attempt


delivery_service = DeliveryService()