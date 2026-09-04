"""
Application and Database Health Verification
"""

from datetime import datetime, timezone
from typing import Any, Dict
from app.core.config import get_settings
from app.core.database import verify_database_connection
from app.core.exceptions import DatabaseUnavailableException
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def get_app_health() -> Dict[str, Any]:
    """Returns basic application liveness health status."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_database_health() -> Dict[str, Any]:
    """
    Executes live query against PostgreSQL to verify connectivity and latency.
    Fails clearly if database is unreachable.
    """
    try:
        db_status = verify_database_connection()
        return {
            "status": "healthy",
            "database": "healthy",
            "latency_ms": db_status.get("latency_ms"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except DatabaseUnavailableException as exc:
        return {
            "status": "unhealthy",
            "database": "unhealthy",
            "error": exc.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
