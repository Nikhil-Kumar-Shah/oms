"""
Issue & Escalation Register SQLAlchemy Models
Paradox Sports OMS - Phase 3 Core Operational System
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class IssueSensitivity(str, enum.Enum):
    NORMAL = "NORMAL"
    SENSITIVE = "SENSITIVE"
    CONFIDENTIAL = "CONFIDENTIAL"


class Issue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "issues"

    date_raised = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_reference = Column(String(255), nullable=True)

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)

    raised_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_to_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    sensitivity = Column(
        Enum(IssueSensitivity, name="issue_sensitivity_enum", native_enum=True),
        nullable=False,
        default=IssueSensitivity.NORMAL,
        index=True,
    )
    status = Column(
        Enum(IssueStatus, name="issue_status_enum", native_enum=True),
        nullable=False,
        default=IssueStatus.OPEN,
        index=True,
    )

    action_required = Column(Text, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    escalation_target = Column(String(255), nullable=True)
    escalation_action = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    resolution_date = Column(DateTime(timezone=True), nullable=True)
    evidence_link = Column(String(1000), nullable=True)
    remarks = Column(Text, nullable=True)

    # Relationships
    vertical = relationship("Vertical")
    raised_by = relationship("User", foreign_keys=[raised_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    history_entries = relationship("IssueHistory", back_populates="issue", cascade="all, delete-orphan", order_by="desc(IssueHistory.timestamp)")
    issue_assignees = relationship("IssueAssignee", back_populates="issue", cascade="all, delete-orphan")
    comments = relationship("IssueComment", back_populates="issue", cascade="all, delete-orphan", order_by="desc(IssueComment.created_at)")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, title='{self.title}', status='{self.status}', sensitivity='{self.sensitivity}')>"


class IssueAssignee(Base):
    __tablename__ = "issue_assignees"

    issue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    issue = relationship("Issue", back_populates="issue_assignees")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<IssueAssignee(issue_id={self.issue_id}, user_id={self.user_id})>"


class IssueHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "issue_history"

    issue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False)
    details = Column(JSONB, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    correlation_id = Column(String(64), nullable=True)

    # Relationships
    issue = relationship("Issue", back_populates="history_entries")
    actor = relationship("User")

    def __repr__(self) -> str:
        return f"<IssueHistory(id={self.id}, issue_id={self.issue_id}, action='{self.action}')>"


class IssueComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "issue_comments"

    issue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)

    # Relationships
    issue = relationship("Issue", back_populates="comments")
    author = relationship("User")

    def __repr__(self) -> str:
        return f"<IssueComment(id={self.id}, issue_id={self.issue_id}, author_id={self.author_id})>"
