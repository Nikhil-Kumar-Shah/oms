"""
Audit Trail & Immutability Test Suite
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from app.core.exceptions import ImmutableAuditException
from app.services.audit_service import AuditService


def test_audit_log_creation_and_sanitization(db_session: Session, admin_user):
    """Verifies audit log records events and sanitizes sensitive keys."""
    audit = AuditService(db_session)
    actor_id = admin_user.id
    log = audit.log(
        action="TEST_ACTION",
        resource_type="USER",
        resource_id="123",
        outcome="SUCCESS",
        actor_id=actor_id,
        details={"username": "alice", "password": "SecretPassword123", "token": "sensitive_raw_token"},
    )
    db_session.commit()

    assert log.id is not None
    assert log.details is not None
    assert "username" in log.details
    # Verify sensitive keys are stripped
    assert "password" not in log.details
    assert "token" not in log.details


def test_audit_log_immutability(db_session: Session):
    """Verifies that audit records cannot be modified or deleted via service layer."""
    audit = AuditService(db_session)
    dummy_id = uuid.uuid4()

    with pytest.raises(ImmutableAuditException):
        audit.update_record(dummy_id)

    with pytest.raises(ImmutableAuditException):
        audit.delete_record(dummy_id)
