"""
Append-Only Audit Service
Guarantees immutability and records security and administrative actions.
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import ImmutableAuditException
from app.core.logging import get_logger
from app.models.audit import AuditLog

logger = get_logger(__name__)


class AuditService:
    """Manages creation and retrieval of immutable audit events."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        outcome: str = "SUCCESS",
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Appends a new audit record to PostgreSQL.
        Never stores passwords, secrets, or raw session tokens in details.
        """
        safe_details = details.copy() if details else {}
        # Sanitize any accidental sensitive keys
        for key in ["password", "token", "password_hash", "secret"]:
            safe_details.pop(key, None)

        record = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            outcome=outcome,
            actor_id=actor_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            details=safe_details if safe_details else None,
        )
        self.db.add(record)
        self.db.flush()
        logger.info(
            f"AUDIT [{outcome}]: action={action} resource={resource_type}:{resource_id} actor={actor_id}"
        )
        return record

    def list_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        actor_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> List[AuditLog]:
        """Lists audit logs in reverse chronological order."""
        from sqlalchemy.orm import selectinload
        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.actor))
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if outcome:
            stmt = stmt.where(AuditLog.outcome == outcome)
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """Returns total audit record count."""
        stmt = select(AuditLog)
        return len(list(self.db.scalars(stmt).all()))

    def update_record(self, record_id: uuid.UUID, *args, **kwargs) -> None:
        """Prohibited operation: Audit records are strictly immutable."""
        raise ImmutableAuditException("Audit log records cannot be updated or edited")

    def delete_record(self, record_id: uuid.UUID, *args, **kwargs) -> None:
        """Prohibited operation: Audit records cannot be deleted."""
        raise ImmutableAuditException("Audit log records cannot be deleted")
