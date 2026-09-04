"""
Meetings, Participants & Action Items SQLAlchemy Models
Paradox Sports OMS - Phase 4 Event + Coordination System
"""

import enum
import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.task import TaskPriority


class MeetingType(str, enum.Enum):
    INTERNAL_SYNC = "INTERNAL_SYNC"
    VERTICAL_REVIEW = "VERTICAL_REVIEW"
    CORE_COORDINATION = "CORE_COORDINATION"
    CROSS_VERTICAL = "CROSS_VERTICAL"
    EVENT_BRIEFING = "EVENT_BRIEFING"
    DEBRIEF = "DEBRIEF"
    EMERGENCY = "EMERGENCY"
    EVENT_TEAM_SYNC = "EVENT_TEAM_SYNC"
    ORIENTING = "ORIENTING"
    OTHER = "OTHER"


class MeetingStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class RSVPStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    TENTATIVE = "TENTATIVE"


class Meeting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "meetings"

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    organizer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    meeting_type = Column(
        Enum(MeetingType, name="meeting_type_enum", native_enum=True),
        nullable=False,
        default=MeetingType.INTERNAL_SYNC,
        index=True,
    )
    status = Column(
        Enum(MeetingStatus, name="meeting_status_enum", native_enum=True),
        nullable=False,
        default=MeetingStatus.SCHEDULED,
        index=True,
    )

    meeting_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    location = Column(String(255), nullable=True)
    meeting_url = Column(String(1024), nullable=True)
    remarks = Column(Text, nullable=True)

    # Request workflow tracking (Phase 4 Workflow Automation)
    is_requested = Column(Boolean, nullable=False, default=False, index=True)
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    organizer = relationship("User", foreign_keys=[organizer_id], backref="organized_meetings")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    vertical = relationship("Vertical", foreign_keys=[vertical_id], backref="meetings")
    event = relationship("Event", foreign_keys=[event_id], backref="meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    action_items = relationship("MeetingActionItem", back_populates="meeting", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Meeting(id={self.id}, title='{self.title}', status='{self.status}')>"


class MeetingParticipant(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "meeting_participants"
    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_participant_meeting_user"),
    )

    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rsvp_status = Column(
        Enum(RSVPStatus, name="rsvp_status_enum", native_enum=True),
        nullable=False,
        default=RSVPStatus.PENDING,
    )
    invited_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id], backref="meeting_participations")

    def __repr__(self) -> str:
        return f"<MeetingParticipant(meeting_id={self.meeting_id}, user_id={self.user_id}, rsvp='{self.rsvp_status}')>"


class MeetingActionItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "meeting_action_items"

    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=False)
    assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority = Column(
        Enum(TaskPriority, name="task_priority_enum", native_enum=True),
        nullable=False,
        default=TaskPriority.MEDIUM,
    )
    due_date = Column(DateTime(timezone=True), nullable=True)

    # Conversion tracking
    is_converted = Column(Boolean, nullable=False, default=False, index=True)
    converted_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    converted_at = Column(DateTime(timezone=True), nullable=True)
    converted_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="action_items")
    assignee = relationship("User", foreign_keys=[assignee_id])
    converted_task = relationship("Task", foreign_keys=[converted_task_id])
    converted_by = relationship("User", foreign_keys=[converted_by_id])

    def __repr__(self) -> str:
        return f"<MeetingActionItem(id={self.id}, meeting_id={self.meeting_id}, is_converted={self.is_converted})>"
