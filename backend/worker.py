import logging
import os
import time
from urllib.parse import quote

from celery import Celery

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_db = os.getenv("REDIS_DB", "0")
redis_password = os.getenv("REDIS_PASSWORD", "")
redis_scheme = "rediss" if os.getenv("REDIS_TLS", "false").lower() == "true" else "redis"
redis_credentials = f":{quote(redis_password, safe='')}@" if redis_password else ""
redis_tls_query = "?ssl_cert_reqs=required" if redis_scheme == "rediss" else ""
redis_url = os.getenv(
    "REDIS_URL",
    f"{redis_scheme}://{redis_credentials}{redis_host}:{redis_port}/{redis_db}{redis_tls_query}",
)

# Configure Celery to use Redis as the message broker
celery = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", redis_url),
    backend=os.getenv("CELERY_RESULT_BACKEND", redis_url),
)
celery.conf.update(task_track_started=True)


@celery.task
def write_log_celery(message: str):
    time.sleep(float(os.getenv("TASK_DURATION_SECONDS", "10")))
    logger.info("%s", message)
    return f"Task completed: {message}"

