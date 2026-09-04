"""
Tests for Database Connection and Pooling
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import engine, verify_database_connection
from app.core.exceptions import DatabaseUnavailableException


def test_postgres_live_connection():
    """Verifies that verify_database_connection executes SELECT 1 and returns status."""
    result = verify_database_connection()
    assert result["status"] == "healthy"
    assert "latency_ms" in result
    assert result["latency_ms"] > 0


def test_postgres_session_query(db_session: Session):
    """Verifies active session executes queries directly on PostgreSQL."""
    query = text("SELECT 1 AS num, current_database() AS dbname;")
    row = db_session.execute(query).mappings().first()
    assert row is not None
    assert row["num"] == 1
    assert row["dbname"] is not None


def test_engine_pool_settings():
    """Verifies connection pool configuration on SQLAlchemy engine."""
    assert engine.pool.size() >= 1
