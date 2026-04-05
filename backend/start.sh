#!/bin/bash
set -e

# Runs ONLY the API server.
# The Celery worker is a separate Render Background Worker service.
# Its start command is:
#   celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"