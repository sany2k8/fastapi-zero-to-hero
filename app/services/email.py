"""Email delivery stub, invoked via FastAPI BackgroundTasks.

In production, swap the body for a real provider (SES, SendGrid, SMTP) or —
for anything with retries/scheduling — a proper queue (Celery, ARQ, RQ).
The call sites don't change.
"""

import structlog

logger = structlog.get_logger(__name__)


def send_welcome_email(email: str, full_name: str) -> None:
    logger.info("welcome_email_sent", to=email, name=full_name)
