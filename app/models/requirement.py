"""
Cross-Vertical Requirements & Messages SQLAlchemy Models
Paradox Sports OMS - Phase 4 Event + Coordination System
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RequirementPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RequirementStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    # Redesigned workflow statuses
    RAISED = "RAISED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    AWAITING_INFO = "AWAITING_INFO"
    FORWARDED = "FORWARDED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "requirements"

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)

    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    responsible_poc_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    forward_history = Column(
        JSON,
        nullable=False,
        default=list,
    )

    requesting_vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    target_vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    requester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    priority = Column(
        Enum(RequirementPriority, name="requirement_priority_enum", native_enum=True),
        nullable=False,
        default=RequirementPriority.MEDIUM,
        index=True,
    )
    status = Column(
        Enum(RequirementStatus, name="requirement_status_enum", native_enum=True),
        nullable=False,
        default=RequirementStatus.RAISED,
        index=True,
    )

    deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    remarks = Column(Text, nullable=True)
    reference_link = Column(String(1024), nullable=True)

    # Escalation fields (Phase 4 Workflow Automation)
    is_escalated = Column(Boolean, nullable=False, default=False, index=True)
    escalated_to_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    escalated_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalation_reason = Column(Text, nullable=True)
    escalation_status = Column(String(50), nullable=True)  # e.g., "PENDING_REVIEW", "RESOLVED"
    escalation_resolved_at = Column(DateTime(timezone=True), nullable=True)
    escalation_resolved_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalation_resolution_notes = Column(Text, nullable=True)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id], backref="requirements")
    responsible_poc = relationship("User", foreign_keys=[responsible_poc_id], backref="poc_requirements")
    requesting_vertical = relationship("Vertical", foreign_keys=[requesting_vertical_id], backref="outbound_requirements")
    target_vertical = relationship("Vertical", foreign_keys=[target_vertical_id], backref="inbound_requirements")
    requester = relationship("User", foreign_keys=[requester_id], backref="requested_requirements")
    assignee = relationship("User", foreign_keys=[assignee_id], backref="assigned_requirements")
    escalated_to = relationship("User", foreign_keys=[escalated_to_id])
    escalated_by = relationship("User", foreign_keys=[escalated_by_id])
    escalation_resolved_by = relationship("User", foreign_keys=[escalation_resolved_by_id])
    messages = relationship("RequirementMessage", back_populates="requirement", cascade="all, delete-orphan", order_by="RequirementMessage.created_at")

    def __repr__(self) -> str:
        return f"<Requirement(id={self.id}, title='{self.title}', status='{self.status}')>"


class RequirementMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "requirement_messages"

    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    requirement = relationship("Requirement", back_populates="messages")
    author = relationship("User", foreign_keys=[author_id])

    def __repr__(self) -> str:
        return f"<RequirementMessage(id={self.id}, requirement_id={self.requirement_id}, author_id={self.author_id})>"
