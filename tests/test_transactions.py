"""
Tests for Transaction Lifecycle: Commit, Rollback, and Isolation
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.test_record import SystemTestRecord
from app.schemas.test_record import SystemTestRecordCreate
from app.services.test_record_service import SystemTestRecordService


def test_transaction_commit_success(db_session: Session):
    """
    Verifies that a normal transaction commits data to PostgreSQL and assigns primary key.
    """
    service = SystemTestRecordService(db_session)
    name = f"Tx-Commit-Test-{uuid.uuid4().hex[:6]}"
    record = service.create(SystemTestRecordCreate(name=name, description="Testing commit"))

    assert record.id is not None

    # Verify query in new session or query directly
    stmt = select(SystemTestRecord).where(SystemTestRecord.id == record.id)
    persisted = db_session.scalar(stmt)
    assert persisted is not None
    assert persisted.name == name


def test_transaction_rollback_on_error(db_session: Session):
    """
    Verifies that on an unhandled exception or explicit error, the transaction rolls back
    and leaves ZERO partial state in PostgreSQL.
    """
    initial_count = len(list(db_session.scalars(select(SystemTestRecord)).all()))

    failed_name = f"Tx-Fail-{uuid.uuid4().hex[:6]}"

    with pytest.raises(Exception):
        # Manually create record, simulate failure before commit
        record = SystemTestRecord(name=failed_name, description="Should be rolled back")
        db_session.add(record)
        db_session.flush()  # Flushed to DB transaction

        # Force an intentional exception
        raise ValueError("Simulated unexpected failure during transaction processing")

    db_session.rollback()

    # Verify that the rolled back record does NOT exist in PostgreSQL
    stmt = select(SystemTestRecord).where(SystemTestRecord.name == failed_name)
    found = db_session.scalar(stmt)
    assert found is None

    final_count = len(list(db_session.scalars(select(SystemTestRecord)).all()))
    assert final_count == initial_count
