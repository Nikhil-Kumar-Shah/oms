"""
Audit Log Model (Append-Only & Immutable)
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """
    Append-Only Audit Log Record.
    Records security, authentication, administrative and state change actions.
    Audit records are immutable and must never be altered or deleted.
    """

    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="User ID of the actor initiating the action (null for system/unauthenticated)",
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Action performed (e.g. AUTH_LOGIN, USER_CREATE, ROLE_ASSIGN)",
    )

    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Type of target resource (e.g. USER, VERTICAL, SESSION)",
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="ID of target resource",
    )

    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SUCCESS",
        index=True,
        doc="Outcome: SUCCESS, FAILURE, DENIED",
    )

    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="HTTP Request correlation ID",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        doc="Client IP address",
    )

    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Safe contextual metadata (never secrets or passwords)",
    )

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', outcome='{self.outcome}')>"
