"""
Events, Event Members & Event Readiness SQLAlchemy Models
Paradox Sports OMS - Phase 4 Event + Coordination System
"""

import enum
import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EventType(str, enum.Enum):
    TOURNAMENT = "TOURNAMENT"
    MATCH = "MATCH"
    WORKSHOP = "WORKSHOP"
    CEREMONY = "CEREMONY"
    TRAINING = "TRAINING"
    MEETING = "MEETING"
    OTHER = "OTHER"


class EventStatus(str, enum.Enum):
    PLANNING = "PLANNING"
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class EventMemberRole(str, enum.Enum):
    HEAD = "HEAD"
    POC = "POC"
    COORDINATOR = "COORDINATOR"
    VOLUNTEER = "VOLUNTEER"
    MEMBER = "MEMBER"


class EventMemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"


class ReadinessCategory(str, enum.Enum):
    PLANNING = "PLANNING"
    COORDINATION = "COORDINATION"
    DOCUMENTATION = "DOCUMENTATION"
    COMMUNICATIONS = "COMMUNICATIONS"
    TECHNICAL_PREPARATION = "TECHNICAL_PREPARATION"
    MOCK_TRIAL = "MOCK_TRIAL"
    FINAL_APPROVAL = "FINAL_APPROVAL"
    EXECUTION_READINESS = "EXECUTION_READINESS"


class ReadinessStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "events"

    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    event_type = Column(
        Enum(EventType, name="event_type_enum", native_enum=True),
        nullable=False,
        default=EventType.TOURNAMENT,
        index=True,
    )
    status = Column(
        Enum(EventStatus, name="event_status_enum", native_enum=True),
        nullable=False,
        default=EventStatus.PLANNING,
        index=True,
    )
    planned_date = Column(Date, nullable=True, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    location = Column(String(255), nullable=True)
    society_name = Column(String(255), nullable=True)

    event_head_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    primary_poc_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    resource_links = Column(JSONB, nullable=False, default=dict)
    remarks = Column(Text, nullable=True)

    # Relationships
    vertical = relationship("Vertical", backref="events")
    event_head = relationship("User", foreign_keys=[event_head_id], backref="headed_events")
    primary_poc = relationship("User", foreign_keys=[primary_poc_id], backref="poc_events")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_events")
    members = relationship("EventMember", back_populates="event", cascade="all, delete-orphan")
    readiness_items = relationship("EventReadinessItem", back_populates="event", cascade="all, delete-orphan")
    event_team_profiles = relationship("EventTeamProfile", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, name='{self.name}', status='{self.status}')>"


class EventMember(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "event_members"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_member_event_user"),
    )

    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_in_event = Column(
        Enum(EventMemberRole, name="event_member_role_enum", native_enum=True),
        nullable=False,
        default=EventMemberRole.COORDINATOR,
    )
    status = Column(
        Enum(EventMemberStatus, name="event_member_status_enum", native_enum=True),
        nullable=False,
        default=EventMemberStatus.ACTIVE,
    )
    assigned_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    notes = Column(Text, nullable=True)

    # Relationships
    event = relationship("Event", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], backref="event_memberships")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    def __repr__(self) -> str:
        return f"<EventMember(event_id={self.event_id}, user_id={self.user_id}, role='{self.role_in_event}')>"


class EventReadinessItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "event_readiness_items"

    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(
        Enum(ReadinessCategory, name="readiness_category_enum", native_enum=True),
        nullable=False,
        default=ReadinessCategory.PLANNING,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ReadinessStatus, name="readiness_status_enum", native_enum=True),
        nullable=False,
        default=ReadinessStatus.NOT_STARTED,
        index=True,
    )
    assigned_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deadline = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_link = Column(String(1024), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    event = relationship("Event", back_populates="readiness_items")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])

    def __repr__(self) -> str:
        return f"<EventReadinessItem(id={self.id}, event_id={self.event_id}, category='{self.category}', status='{self.status}')>"


class EventTeamProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Structured Event Team Operational Profile Metadata.
    1:1 relationship with an EVENT_TEAM User, linked to an Event.
    """

    __tablename__ = "event_team_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    team_name = Column(String(255), nullable=False, index=True)
    head_name = Column(String(255), nullable=True)
    head_email = Column(String(255), nullable=True)
    head_phone = Column(String(50), nullable=True)
    members_summary = Column(JSONB, nullable=False, default=list)
    contact_info = Column(JSONB, nullable=False, default=dict)
    event_metadata = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="event_team_profile")
    event = relationship("Event", back_populates="event_team_profiles")

    def __repr__(self) -> str:
        return f"<EventTeamProfile(id={self.id}, team_name='{self.team_name}', event_id={self.event_id})>"
