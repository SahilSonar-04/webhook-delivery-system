import uuid
import asyncio
import json
import re
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import structlog

from app.workers.celery_app import celery_app
from app.workers.metrics import push_ai_analysis
from app.models.delivery import DeliveryAttempt, AIFailureAnalysis
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def make_session() -> tuple:
    engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_size=1,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def run_ai_analysis(attempt_id: str, correlation_id: str | None = None):
    """Analyze failed delivery using Groq AI."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id or str(uuid.uuid4()),
        attempt_id=attempt_id,
    )

    engine, session_factory = make_session()

    try:
        async with session_factory() as db:
            result = await db.execute(
                select(DeliveryAttempt)
                .options(selectinload(DeliveryAttempt.event))
                .where(DeliveryAttempt.id == uuid.UUID(attempt_id))
            )
            attempt = result.scalar_one_or_none()

            if not attempt:
                logger.error("ai_analysis.attempt_not_found")
                return

            # Idempotency guard — skip if already analyzed
            existing = await db.execute(
                select(AIFailureAnalysis).where(
                    AIFailureAnalysis.delivery_attempt_id == attempt.id
                )
            )
            if existing.scalar_one_or_none():
                logger.info("ai_analysis.already_exists")
                return

            context = {
                "event_type": attempt.event.event_type,
                "attempt_number": attempt.attempt_number,
                "error_message": attempt.error_message,
                "response_code": attempt.response_code,
                "response_body": attempt.response_body,
                "duration_ms": attempt.duration_ms,
            }

            analysis = None

            try:
                from groq import Groq
                client = Groq(api_key=settings.GROQ_API_KEY)

                prompt = f"""
You are a webhook delivery system expert. Analyze this failed webhook delivery and respond ONLY with valid JSON.

Failed delivery context:
{json.dumps(context, indent=2)}

Respond with exactly this JSON structure:
{{
    "failure_category": "one of: server_down, timeout, ssl_error, dns_error, http_4xx, http_5xx, connection_refused, unknown",
    "explanation": "clear explanation of what went wrong in 2-3 sentences",
    "suggested_fix": "specific actionable steps to fix this in 2-3 sentences",
    "confidence_score": 0.95,
    "severity": "one of: low, medium, high, critical"
}}
"""

                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )

                raw = response.choices[0].message.content.strip()

                # Strip optional ```json ... ``` or ``` ... ``` fences robustly.
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw).strip()

                analysis_data = json.loads(raw)

                analysis = AIFailureAnalysis(
                    id=uuid.uuid4(),
                    delivery_attempt_id=attempt.id,
                    failure_category=analysis_data.get("failure_category", "unknown"),
                    explanation=analysis_data.get("explanation", ""),
                    suggested_fix=analysis_data.get("suggested_fix", ""),
                    confidence_score=float(analysis_data.get("confidence_score", 0.5)),
                    severity=analysis_data.get("severity", "medium"),
                )
                logger.info(
                    "ai_analysis.completed",
                    failure_category=analysis.failure_category,
                    severity=analysis.severity,
                    confidence_score=analysis.confidence_score,
                )

            except Exception as e:
                logger.error("ai_analysis.failed", error=str(e))
                analysis = AIFailureAnalysis(
                    id=uuid.uuid4(),
                    delivery_attempt_id=attempt.id,
                    failure_category="unknown",
                    explanation=f"Automated analysis unavailable. Raw error: {attempt.error_message}",
                    suggested_fix="Check subscriber server logs and verify the target URL is reachable.",
                    confidence_score=0.0,
                    severity="medium",
                )

            if analysis:
                db.add(analysis)
                await db.commit()
                push_ai_analysis(
                    failure_category=analysis.failure_category,
                    severity=analysis.severity,
                )

    finally:
        await engine.dispose()


@celery_app.task(name="analyze_failure")
def analyze_failure(attempt_id: str, correlation_id: str | None = None):
    asyncio.run(run_ai_analysis(attempt_id, correlation_id))
