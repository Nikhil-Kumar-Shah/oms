"""
Master Calendar SQLAlchemy Models
Paradox Sports OMS - Phase 3 Core Operational System
"""

import enum
import uuid
from datetime import date, time
from typing import Optional
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActivityCategory(str, enum.Enum):
    ACTIVITY = "ACTIVITY"
    MILESTONE = "MILESTONE"
    REVIEW_MEETING = "REVIEW_MEETING"
    INTERVIEW = "INTERVIEW"
    REPORT_DEADLINE = "REPORT_DEADLINE"
    ONBOARDING = "ONBOARDING"
    ORIENTATION = "ORIENTATION"
    EVENT = "EVENT"
    MEETING = "MEETING"


class CalendarPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CalendarStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    UPCOMING = "UPCOMING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class DeadlineType(str, enum.Enum):
    HARD_DEADLINE = "HARD_DEADLINE"
    SOFT_DEADLINE = "SOFT_DEADLINE"
    INFORMATIONAL = "INFORMATIONAL"


class CalendarAudience(str, enum.Enum):
    ALL = "ALL"
    ORGANIZATION = "ORGANIZATION"
    VERTICAL = "VERTICAL"
    SPECIFIC_USERS = "SPECIFIC_USERS"


class RecurrenceFrequency(str, enum.Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class CalendarEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "calendar_entries"

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    activity_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    category = Column(
        Enum(ActivityCategory, name="activity_category_enum", native_enum=True),
        nullable=False,
        default=ActivityCategory.ACTIVITY,
        index=True,
    )
    priority = Column(
        Enum(CalendarPriority, name="calendar_priority_enum", native_enum=True),
        nullable=False,
        default=CalendarPriority.MEDIUM,
        index=True,
    )
    status = Column(
        Enum(CalendarStatus, name="calendar_status_enum", native_enum=True),
        nullable=False,
        default=CalendarStatus.PLANNED,
        index=True,
    )
    deadline_type = Column(
        Enum(DeadlineType, name="deadline_type_enum", native_enum=True),
        nullable=False,
        default=DeadlineType.INFORMATIONAL,
        index=True,
    )
    audience = Column(
        Enum(CalendarAudience, name="calendar_audience_enum", native_enum=True),
        nullable=False,
        default=CalendarAudience.ORGANIZATION,
        index=True,
    )

    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_reference = Column(String(255), nullable=True)
    resource_link = Column(String(1000), nullable=True)
    remarks = Column(Text, nullable=True)

    # Recurrence support
    recurrence = Column(
        Enum(RecurrenceFrequency, name="recurrence_frequency_enum", native_enum=True),
        nullable=False,
        default=RecurrenceFrequency.NONE,
        index=True,
    )
    recurrence_end_date = Column(Date, nullable=True)

    # Reschedule tracking
    original_date = Column(Date, nullable=True)
    rescheduled_at = Column(DateTime(timezone=True), nullable=True)

    # Entity links
    entity_type = Column(String(50), nullable=True, default="CALENDAR_ENTRY", index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
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

    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    vertical = relationship("Vertical")
    created_by = relationship("User", foreign_keys=[created_by_id])
    task = relationship("Task", foreign_keys=[task_id])
    event = relationship("Event", foreign_keys=[event_id])
    meeting = relationship("Meeting", foreign_keys=[meeting_id])
    requirement = relationship("Requirement", foreign_keys=[requirement_id])
    entry_users = relationship("CalendarEntryUser", back_populates="calendar_entry", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CalendarEntry(id={self.id}, title='{self.title}', date={self.activity_date})>"


class CalendarEntryUser(Base):
    __tablename__ = "calendar_entry_users"

    calendar_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("calendar_entries.id", ondelete="CASCADE"),
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
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    calendar_entry = relationship("CalendarEntry", back_populates="entry_users")
    user = relationship("User")

