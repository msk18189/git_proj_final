"""Celery application configuration for PRISM background job processing.

The Celery worker handles repository sync jobs asynchronously, providing:
- Persistent job state (survives backend restarts)
- Retry logic for transient failures
- Rate limit backoff handling
- Task status tracking via SyncJob model

Usage:
    celery -A celery_app worker --loglevel=info --concurrency=2
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "prism",
    broker=CELERY_BROKER_URL,
    include=["tasks.sync_task"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Reliability
    task_acks_late=True,                    # Ack after task completes (crash recovery)
    worker_prefetch_multiplier=1,           # Don't prefetch extra tasks
    task_reject_on_worker_lost=True,        # Re-queue if worker dies
    task_track_started=True,                # Track STARTED state

    # Connection
    broker_connection_retry_on_startup=True,

    # Concurrency: limit to 2 concurrent syncs to avoid GitHub rate limits
    worker_concurrency=2,

    # Timeouts
    task_soft_time_limit=1800,              # 30 min soft limit
    task_time_limit=2400,                   # 40 min hard limit
)
