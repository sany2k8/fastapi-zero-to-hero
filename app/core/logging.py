"""Structured logging with structlog.

Console renderer for local development, JSON lines for production
(set LOG_JSON=true). Request-scoped fields (request_id, method, path)
are bound via structlog contextvars in the request middleware.
"""

import logging

import structlog

from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    # Our middleware writes structured access logs; silence uvicorn's duplicate ones.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
