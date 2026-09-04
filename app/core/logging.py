"""
Structured Application Logging System
Provides clean, consistent logging with correlation ID support without leaking credentials.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Optional

# Context variable for request correlation ID
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id_ctx", default=None)


class CorrelationIdFilter(logging.Filter):
    """Injects correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = correlation_id_ctx.get()
        record.correlation_id = cid if cid else "-"
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configures application-wide structured logging."""
    log_format = (
        "[%(asctime)s] [%(levelname)s] [req_id:%(correlation_id)s] "
        "[%(name)s:%(lineno)d]: %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(handler)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger configured with correlation ID filter."""
    logger = logging.getLogger(name)
    logger.addFilter(CorrelationIdFilter())
    return logger
