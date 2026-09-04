"""
Communication Models
Includes Announcements, Directives, Directive Acknowledgements, Notifications, and Communication Logs.
"""

import enum
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnnouncementPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AnnouncementScope(str, enum.Enum):
    ALL = "ALL"
    ORGANIZATION = "ORGANIZATION"
    VERTICAL = "VERTICAL"
    USER = "USER"
    EVENT = "EVENT"
    EVENT_TEAM = "EVENT_TEAM"


class AnnouncementStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class Announcement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Broadcast information targeted to organization, vertical, user, event, or event team."""

    __tablename__ = "announcements"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="GENERAL")
    priority: Mapped[AnnouncementPriority] = mapped_column(
        Enum(AnnouncementPriority, name="announcement_priority_enum", native_enum=True),
        nullable=False,
        default=AnnouncementPriority.NORMAL,
    )
    scope: Mapped[AnnouncementScope] = mapped_column(
        Enum(AnnouncementScope, name="announcement_scope_enum", native_enum=True),
        nullable=False,
        default=AnnouncementScope.ALL,
    )
    vertical_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AnnouncementStatus] = mapped_column(
        Enum(AnnouncementStatus, name="announcement_status_enum", native_enum=True),
        nullable=False,
        default=AnnouncementStatus.DRAFT,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    author = relationship("User", foreign_keys=[author_id], lazy="joined")
    vertical = relationship("Vertical", foreign_keys=[vertical_id], lazy="joined")
    event = relationship("Event", foreign_keys=[event_id], lazy="joined")
    target_user = relationship("User", foreign_keys=[target_user_id], lazy="joined")

    __table_args__ = (
        Index("ix_announcements_status", "status"),
        Index("ix_announcements_published_at", "published_at"),
        Index("ix_announcements_vertical_id", "vertical_id"),
        Index("ix_announcements_event_id", "event_id"),
    )


class DirectivePriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DirectiveScope(str, enum.Enum):
    ALL = "ALL"
    VERTICAL = "VERTICAL"
    USER = "USER"


class DirectiveStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class Directive(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational instructions or governance mandates that require compliance."""

    __tablename__ = "directives"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope: Mapped[DirectiveScope] = mapped_column(
        Enum(DirectiveScope, name="directive_scope_enum", native_enum=True),
        nullable=False,
        default=DirectiveScope.ALL,
    )
    vertical_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    priority: Mapped[DirectivePriority] = mapped_column(
        Enum(DirectivePriority, name="directive_priority_enum", native_enum=True),
        nullable=False,
        default=DirectivePriority.MEDIUM,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[DirectiveStatus] = mapped_column(
        Enum(DirectiveStatus, name="directive_status_enum", native_enum=True),
        nullable=False,
        default=DirectiveStatus.DRAFT,
    )
    requires_acknowledgement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    issued_by = relationship("User", foreign_keys=[issued_by_id], lazy="joined")
    vertical = relationship("Vertical", foreign_keys=[vertical_id], lazy="joined")
    target_user = relationship("User", foreign_keys=[target_user_id], lazy="joined")
    acknowledgements = relationship(
        "DirectiveAcknowledgement",
        back_populates="directive",
        cascade="all, delete-orphan",
        order_by="DirectiveAcknowledgement.created_at",
    )

    __table_args__ = (
        Index("ix_directives_status", "status"),
        Index("ix_directives_vertical_id", "vertical_id"),
        Index("ix_directives_effective_date", "effective_date"),
    )


class AcknowledgementStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class DirectiveAcknowledgement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit individual acknowledgement record for a directive."""

    __tablename__ = "directive_acknowledgements"

    directive_id: Mapped[UUID] = mapped_column(
        ForeignKey("directives.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AcknowledgementStatus] = mapped_column(
        Enum(AcknowledgementStatus, name="acknowledgement_status_enum", native_enum=True),
        nullable=False,
        default=AcknowledgementStatus.PENDING,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    directive = relationship("Directive", back_populates="acknowledgements")
    user = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("directive_id", "user_id", name="uq_directive_user_acknowledgement"),
        Index("ix_directive_ack_user_id", "user_id"),
    )


class NotificationType(str, enum.Enum):
    TASK = "TASK"
    REQUIREMENT = "REQUIREMENT"
    MEETING = "MEETING"
    DIRECTIVE = "DIRECTIVE"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    TRANSFER = "TRANSFER"
    FORM = "FORM"
    REPORT = "REPORT"
    SYSTEM = "SYSTEM"


class NotificationReadStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    DISMISSED = "DISMISSED"


class Notification(Base, UUIDPrimaryKeyMixin):
    """System attention mechanism alerting users to operational changes."""

    __tablename__ = "notifications"

    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type_enum", native_enum=True),
        nullable=False,
        default=NotificationType.SYSTEM,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    read_status: Mapped[NotificationReadStatus] = mapped_column(
        Enum(NotificationReadStatus, name="notification_read_status_enum", native_enum=True),
        nullable=False,
        default=NotificationReadStatus.UNREAD,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    recipient = relationship("User", foreign_keys=[recipient_id], lazy="select")

    @property
    def is_read(self) -> bool:
        return self.read_status == NotificationReadStatus.READ

    __table_args__ = (
        Index("ix_notifications_recipient_read", "recipient_id", "read_status"),
        Index("ix_notifications_recipient_created", "recipient_id", "created_at"),
        Index("ix_notifications_created_at", "created_at"),
    )



class CommunicationType(str, enum.Enum):
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    OFFICIAL_MESSAGE = "OFFICIAL_MESSAGE"
    NOTICE = "NOTICE"
    CALL = "CALL"
    OTHER = "OTHER"


class CommunicationLogStatus(str, enum.Enum):
    RECORDED = "RECORDED"
    ARCHIVED = "ARCHIVED"


class CommunicationLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Formal operational log of important official communication."""

    __tablename__ = "communication_logs"

    date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    communication_type: Mapped[CommunicationType] = mapped_column(
        Enum(CommunicationType, name="communication_type_enum", native_enum=True),
        nullable=False,
        default=CommunicationType.OFFICIAL_MESSAGE,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_info: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_info: Mapped[str] = mapped_column(String(255), nullable=False)
    vertical_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    related_resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    reference_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[CommunicationLogStatus] = mapped_column(
        Enum(CommunicationLogStatus, name="communication_log_status_enum", native_enum=True),
        nullable=False,
        default=CommunicationLogStatus.RECORDED,
    )

    created_by = relationship("User", foreign_keys=[created_by_id], lazy="joined")
    vertical = relationship("Vertical", foreign_keys=[vertical_id], lazy="joined")
    event = relationship("Event", foreign_keys=[event_id], lazy="joined")

    __table_args__ = (
        Index("ix_comm_logs_vertical_id", "vertical_id"),
        Index("ix_comm_logs_event_id", "event_id"),
        Index("ix_comm_logs_date_time", "date_time"),
    )
