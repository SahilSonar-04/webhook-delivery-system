#!/bin/bash
set -e

echo "Starting Celery worker..."
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &

echo "Starting FastAPI..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}