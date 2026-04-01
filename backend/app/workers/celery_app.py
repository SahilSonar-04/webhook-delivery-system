from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "webhook_delivery",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.delivery_worker",
        "app.workers.ai_worker",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,        # task only removed from queue after completion
    task_reject_on_worker_lost=True,  # requeue if worker crashes mid-task
    worker_prefetch_multiplier=1,     # worker takes one task at a time
)