#!/bin/bash
set -e

if [ "${RUN_EMBEDDED_WORKER:-true}" = "true" ]; then
  echo "Starting Celery worker in background..."
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
fi

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"