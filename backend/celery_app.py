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

# SECURITY: In production, set CELERY_BROKER_URL with a password:
#   redis://:your_redis_password@localhost:6379/0
# Configure Redis requirepass in redis.conf on the server.
redis_pw = os.getenv("REDIS_PASSWORD", "")
redis_auth = f":{redis_pw}@" if redis_pw else ""
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"redis://{redis_auth}localhost:6379/0")

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
    worker_prefetch_multiplier=2,           # Increased from 1 to allow slightly better throughput
    task_reject_on_worker_lost=True,        # Re-queue if worker dies
    task_track_started=True,                # Track STARTED state

    # Connection
    broker_connection_retry_on_startup=True,

    # Concurrency: Increased to 10 for better SaaS scalability
    worker_concurrency=10,

    # Timeouts
    task_soft_time_limit=1800,              # 30 min soft limit
    task_time_limit=2400,                   # 40 min hard limit
)
