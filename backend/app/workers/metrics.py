from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _new_registry() -> CollectorRegistry:
    return CollectorRegistry()


def push_delivery_outcome(event_type: str, status: str, attempt_number: int, duration_ms: float | None) -> None:
    """
    Push metrics for a single delivery attempt outcome.
    status is one of: delivered, failed, dead
    """
    registry = _new_registry()

    outcome_counter = Counter(
        "wds_delivery_attempts_total",
        "Total delivery attempts by outcome",
        ["event_type", "status"],
        registry=registry,
    )
    outcome_counter.labels(event_type=event_type, status=status).inc()

    attempt_number_hist = Histogram(
        "wds_delivery_attempt_number",
        "Attempt number at which the delivery reached this outcome",
        ["event_type", "status"],
        buckets=(1, 2, 3, 4, 5, 6),
        registry=registry,
    )
    attempt_number_hist.labels(event_type=event_type, status=status).observe(attempt_number)

    if duration_ms is not None:
        duration_hist = Histogram(
            "wds_delivery_duration_ms",
            "HTTP call duration for a delivery attempt, in milliseconds",
            ["event_type", "status"],
            buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000),
            registry=registry,
        )
        duration_hist.labels(event_type=event_type, status=status).observe(duration_ms)

    try:
        push_to_gateway(settings.PUSHGATEWAY_URL, job="wds_delivery_worker", registry=registry)
    except Exception as e:
        logger.error("metrics.push_failed", error=str(e))


def push_retry_scheduled(event_type: str, retry_in_seconds: int) -> None:
    registry = _new_registry()

    retry_counter = Counter(
        "wds_delivery_retries_total",
        "Total retries scheduled",
        ["event_type"],
        registry=registry,
    )
    retry_counter.labels(event_type=event_type).inc()

    retry_delay_hist = Histogram(
        "wds_delivery_retry_delay_seconds",
        "Scheduled retry delay in seconds",
        ["event_type"],
        buckets=(30, 60, 120, 240, 480, 960, 1920, 3840, 7200),
        registry=registry,
    )
    retry_delay_hist.labels(event_type=event_type).observe(retry_in_seconds)

    try:
        push_to_gateway(settings.PUSHGATEWAY_URL, job="wds_delivery_worker", registry=registry)
    except Exception as e:
        logger.error("metrics.push_failed", error=str(e))


def push_ai_analysis(failure_category: str, severity: str) -> None:
    registry = _new_registry()

    analysis_counter = Counter(
        "wds_ai_analysis_total",
        "Total AI failure analyses performed",
        ["failure_category", "severity"],
        registry=registry,
    )
    analysis_counter.labels(failure_category=failure_category, severity=severity).inc()

    try:
        push_to_gateway(settings.PUSHGATEWAY_URL, job="wds_ai_worker", registry=registry)
    except Exception as e:
        logger.error("metrics.push_failed", error=str(e))
