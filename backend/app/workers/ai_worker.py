import uuid
import asyncio
import json
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.workers.celery_app import celery_app
from app.models.delivery import DeliveryAttempt, AIFailureAnalysis
from app.db.database import AsyncSessionLocal
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)


async def run_ai_analysis(attempt_id: str):
    """Analyze failed delivery using Groq AI."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DeliveryAttempt)
            .options(selectinload(DeliveryAttempt.event))
            .where(DeliveryAttempt.id == uuid.UUID(attempt_id))
        )
        attempt = result.scalar_one_or_none()

        if not attempt:
            return

        # Skip if already analyzed
        existing = await db.execute(
            select(AIFailureAnalysis).where(
                AIFailureAnalysis.delivery_attempt_id == attempt.id
            )
        )
        if existing.scalar_one_or_none():
            return

        # Build context for AI
        context = {
            "event_type": attempt.event.event_type,
            "attempt_number": attempt.attempt_number,
            "error_message": attempt.error_message,
            "response_code": attempt.response_code,
            "response_body": attempt.response_body,
            "duration_ms": attempt.duration_ms,
        }

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
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()

            # Clean JSON if wrapped in backticks
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

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
            db.add(analysis)
            await db.commit()
            logger.info(f"AI analysis complete for {attempt_id}")

        except Exception as e:
            logger.error(f"AI analysis failed for {attempt_id}: {e}")

            # Store fallback analysis so dashboard always shows something
            fallback = AIFailureAnalysis(
                id=uuid.uuid4(),
                delivery_attempt_id=attempt.id,
                failure_category="unknown",
                explanation=f"Automated analysis unavailable. Raw error: {attempt.error_message}",
                suggested_fix="Check subscriber server logs and verify the target URL is reachable.",
                confidence_score=0.0,
                severity="medium",
            )
            db.add(fallback)
            await db.commit()


@celery_app.task(name="analyze_failure")
def analyze_failure(attempt_id: str):
    asyncio.run(run_ai_analysis(attempt_id))