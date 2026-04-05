import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from app.models.delivery import DeliveryAttempt, AIFailureAnalysis
from app.models.event import Event
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
        # Count actual unique events (not delivery attempts)
        event_count_result = await db.execute(
            select(func.count(Event.id))
        )
        total_events = event_count_result.scalar() or 0

        # Count delivery attempts by status
        attempts_result = await db.execute(
            select(
                func.count(DeliveryAttempt.id).label("total_attempts"),
                func.sum(case((DeliveryAttempt.status == "delivered", 1), else_=0)).label("delivered"),
                func.sum(case((DeliveryAttempt.status == "failed", 1), else_=0)).label("failed"),
                func.sum(case((DeliveryAttempt.status == "pending", 1), else_=0)).label("pending"),
                func.sum(case((DeliveryAttempt.status == "delivering", 1), else_=0)).label("delivering"),
                func.sum(case((DeliveryAttempt.status == "dead", 1), else_=0)).label("dead"),
            )
        )
        row = attempts_result.one()
        total_attempts = row.total_attempts or 0
        delivered = int(row.delivered or 0)

        return DashboardStats(
            total_events=total_events,
            total_attempts=total_attempts,
            delivered=delivered,
            failed=int(row.failed or 0),
            pending=int(row.pending or 0),
            delivering=int(row.delivering or 0),
            dead=int(row.dead or 0),
            success_rate=round((delivered / total_attempts * 100), 2) if total_attempts > 0 else 0.0,
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
        # Set to MAX_RETRY_ATTEMPTS - 2 so that after the worker increments
        # attempt_number by 1, it becomes MAX_RETRY_ATTEMPTS - 1, which is
        # still below the dead-letter threshold and delivery is actually
        # attempted. The previous value (MAX_RETRY_ATTEMPTS - 1) caused the
        # worker to increment to MAX_RETRY_ATTEMPTS, immediately hit the >=
        # check, and mark the attempt dead without ever sending the request.
        from app.core.config import settings
        attempt.attempt_number = settings.MAX_RETRY_ATTEMPTS - 2
        attempt.next_retry_at = None
        attempt.error_message = None
        attempt.response_code = None
        attempt.response_body = None
        await db.flush()
        return attempt

    async def recover_stuck_deliveries(self, db: AsyncSession) -> int:
        """
        Reset delivery attempts stuck in 'delivering' state for longer than
        2x the delivery timeout. This handles Celery worker hard crashes.
        Called on startup or via a periodic task.
        """
        from app.core.config import settings
        stuck_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=settings.DELIVERY_TIMEOUT * 2
        )
        result = await db.execute(
            select(DeliveryAttempt).where(
                DeliveryAttempt.status == "delivering",
                DeliveryAttempt.updated_at < stuck_threshold,
            )
        )
        stuck = list(result.scalars().all())
        for attempt in stuck:
            attempt.status = "failed"
            attempt.error_message = "Worker crashed or timed out — reset by recovery job"
        if stuck:
            await db.flush()
        return len(stuck)


delivery_service = DeliveryService()