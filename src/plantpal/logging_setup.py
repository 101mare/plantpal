"""structlog configuration (B.6): JSON in production, colorized console in dev/test.

No PII/secrets in logs — callers hash emails via ``security.hash_email_for_log``
and never pass tokens, API keys, notes or free-text into the event stream.
"""

from __future__ import annotations

import logging

import structlog

from .config import Settings
from .time_utils import now_berlin


def _berlin_timestamp(_, __, event_dict):
    event_dict["ts"] = now_berlin().isoformat()
    return event_dict


def configure_logging(settings: Settings) -> None:
    use_json = settings.LOG_JSON if settings.LOG_JSON is not None else settings.is_production
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)
    renderer = structlog.processors.JSONRenderer() if use_json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _berlin_timestamp,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "plantpal"):
    return structlog.get_logger(name)
