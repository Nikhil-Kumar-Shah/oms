"""
Authoritative PostgreSQL Database Engine & Session Management
Using SQLAlchemy 2.x with explicit connection pooling and transaction lifecycle.
"""

import time
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings
from app.core.exceptions import DatabaseUnavailableException
from app.core.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()

# Create Authoritative SQLAlchemy 2.x PostgreSQL Engine
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,  # Test connections before checkout
        connect_args={"connect_timeout": 5},
        echo=False,
    )
except Exception as exc:
    logger.critical(f"Failed to initialize PostgreSQL engine: {exc}")
    raise

# Session Factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI request-scoped database session dependency.
    Ensures safe transaction boundary and guarantees session cleanup.
    """
    session: Session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error(f"Database error during request session; transaction rolled back: {exc}")
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def verify_database_connection(timeout_seconds: float = 5.0) -> dict:
    """
    Verifies actual PostgreSQL connectivity by executing a live query.
    Returns status metadata with latency measurement.
    Fails fast if PostgreSQL is unavailable.
    """
    start_time = time.perf_counter()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 AS alive, version();")).mappings().first()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if result and result["alive"] == 1:
                return {
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 2),
                    "server_version": result.get("version", "PostgreSQL").split()[0:2],
                }
            raise OperationalError("Query completed but returned unexpected result", params=None, orig=None)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(f"PostgreSQL connection verification failed ({latency_ms:.2f}ms): {exc}")
        raise DatabaseUnavailableException(
            message="PostgreSQL database connection failed or timed out",
            details={"latency_ms": round(latency_ms, 2)},
        ) from exc


def sync_database_enums() -> None:
    """Ensures PostgreSQL native enums include all newly synchronized application enum values."""
    try:
        import psycopg2
        raw_conn = engine.raw_connection()
        raw_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = raw_conn.cursor()
        for val in ["CROSS_VERTICAL", "EVENT_BRIEFING", "DEBRIEF"]:
            try:
                cur.execute(f"ALTER TYPE meeting_type_enum ADD VALUE IF NOT EXISTS '{val}';")
            except Exception:
                pass
        for val in ["ORGANIZATION", "EVENT_TEAM"]:
            try:
                cur.execute(f"ALTER TYPE announcement_scope_enum ADD VALUE IF NOT EXISTS '{val}';")
            except Exception:
                pass
        cur.close()
        raw_conn.close()
    except Exception as exc:
        logger.warning(f"Could not auto-sync PostgreSQL native enums: {exc}")
