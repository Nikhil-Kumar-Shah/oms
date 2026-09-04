"""
Master Task, Task History & Task Comments SQLAlchemy Models
Paradox Sports OMS - Phase 3 Core Operational System
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaskType(str, enum.Enum):
    ROUTINE = "ROUTINE"
    EVENT = "EVENT"
    MILESTONE = "MILESTONE"
    DOCUMENTATION = "DOCUMENTATION"
    MEETING_FOLLOW_UP = "MEETING_FOLLOW_UP"


class TaskPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskHealth(str, enum.Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OVERDUE = "OVERDUE"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "completion_percentage >= 0 AND completion_percentage <= 100",
            name="chk_tasks_completion_percentage",
        ),
    )

    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_to_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    task_type = Column(
        Enum(TaskType, name="task_type_enum", native_enum=True),
        nullable=False,
        default=TaskType.ROUTINE,
        index=True,
    )
    priority = Column(
        Enum(TaskPriority, name="task_priority_enum", native_enum=True),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
    )
    status = Column(
        Enum(TaskStatus, name="task_status_enum", native_enum=True),
        nullable=False,
        default=TaskStatus.NOT_STARTED,
        index=True,
    )
    completion_percentage = Column(Integer, nullable=False, default=0)
    health = Column(
        Enum(TaskHealth, name="task_health_enum", native_enum=True),
        nullable=False,
        default=TaskHealth.ON_TRACK,
        index=True,
    )

    date_assigned = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_on = Column(DateTime(timezone=True), nullable=True)

    blockers = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    latest_update = Column(Text, nullable=True)
    evidence_link = Column(String(1000), nullable=True)
    deficiency = Column(Text, nullable=True)

    # Escalation fields
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
    escalation_reason = Column(Text, nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalation_status = Column(String(50), nullable=True)
    escalation_resolution = Column(Text, nullable=True)
    escalation_resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    vertical = relationship("Vertical", backref="tasks")
    event = relationship("Event", foreign_keys=[event_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], backref="assigned_tasks")

    assigned_by = relationship("User", foreign_keys=[assigned_by_id], backref="delegated_tasks")
    escalated_to = relationship("User", foreign_keys=[escalated_to_id])
    escalated_by = relationship("User", foreign_keys=[escalated_by_id])
    history_entries = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan", order_by="desc(TaskHistory.timestamp)")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan", order_by="desc(TaskComment.created_at)")

    def calculate_health(self) -> TaskHealth:
        """Calculates authoritative health state based on status and deadline."""
        if self.status == TaskStatus.COMPLETED:
            return TaskHealth.COMPLETE
        if self.status == TaskStatus.BLOCKED:
            return TaskHealth.BLOCKED
        if self.deadline:
            deadline = self.deadline if self.deadline.tzinfo is not None else self.deadline.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now > deadline:
                return TaskHealth.OVERDUE
            # If within 24 hours of deadline and under 50% complete -> AT_RISK
            if (deadline - now).total_seconds() < 86400 and self.completion_percentage < 50:
                return TaskHealth.AT_RISK
        return TaskHealth.ON_TRACK

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"


class TaskHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "task_history"

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
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
    previous_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    correlation_id = Column(String(64), nullable=True)

    # Relationships
    task = relationship("Task", back_populates="history_entries")
    actor = relationship("User")

    def __repr__(self) -> str:
        return f"<TaskHistory(id={self.id}, task_id={self.task_id}, action='{self.action}')>"


class TaskComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_comments"

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
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
    task = relationship("Task", back_populates="comments")
    author = relationship("User")

    def __repr__(self) -> str:
        return f"<TaskComment(id={self.id}, task_id={self.task_id}, author_id={self.author_id})>"
