"""
Daily & Weekly Work Reports SQLAlchemy Models
Paradox Sports OMS - Phase 3 Core Operational System
"""

import enum
import uuid
from datetime import date, datetime, timezone
from typing import List
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    RETURNED = "RETURNED"
    FLAGGED = "FLAGGED"


class WeeklyReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    RETURNED = "RETURNED"


class DailyWorkReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "daily_work_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_daily_work_reports_user_date"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    report_date = Column(Date, nullable=False, index=True)

    work_summary = Column(Text, nullable=False)
    tasks_completed = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    issues = Column(Text, nullable=True)
    next_actions = Column(Text, nullable=True)
    evidence_links = Column(String(1000), nullable=True)

    status = Column(
        Enum(DailyReportStatus, name="daily_report_status_enum", native_enum=True),
        nullable=False,
        default=DailyReportStatus.DRAFT,
        index=True,
    )

    reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_comments = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="daily_reports")
    vertical = relationship("Vertical")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    report_tasks = relationship("DailyReportTask", back_populates="report", cascade="all, delete-orphan")
    history_entries = relationship("DailyReportHistory", back_populates="report", cascade="all, delete-orphan", order_by="desc(DailyReportHistory.created_at)")

    @property
    def author_id(self) -> uuid.UUID:
        return self.user_id

    @property
    def task_ids(self) -> List[uuid.UUID]:
        return [rt.task_id for rt in self.report_tasks]

    def __repr__(self) -> str:
        return f"<DailyWorkReport(id={self.id}, user_id={self.user_id}, date={self.report_date}, status='{self.status}')>"


class DailyReportTask(Base):
    __tablename__ = "daily_report_tasks"

    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("daily_work_reports.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    progress_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    report = relationship("DailyWorkReport", back_populates="report_tasks")
    task = relationship("Task")

    def __repr__(self) -> str:
        return f"<DailyReportTask(report_id={self.report_id}, task_id={self.task_id})>"


class DailyReportHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "daily_report_history"

    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("daily_work_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    report = relationship("DailyWorkReport", back_populates="history_entries")
    actor = relationship("User")

    def __repr__(self) -> str:
        return f"<DailyReportHistory(id={self.id}, report_id={self.report_id}, action='{self.action}')>"


class WeeklyReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start_date", name="uq_weekly_reports_user_week_start"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    week_start_date = Column(Date, nullable=False, index=True)
    week_end_date = Column(Date, nullable=False, index=True)

    summary = Column(Text, nullable=False)
    completed_work = Column(Text, nullable=True)
    outstanding_work = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    issues = Column(Text, nullable=True)
    priorities_next_week = Column(Text, nullable=True)

    supervisor_comments = Column(Text, nullable=True)
    reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        Enum(WeeklyReportStatus, name="weekly_report_status_enum", native_enum=True),
        nullable=False,
        default=WeeklyReportStatus.SUBMITTED,
        index=True,
    )
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="weekly_reports")
    vertical = relationship("Vertical")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    @property
    def author_id(self) -> uuid.UUID:
        return self.user_id

    def __repr__(self) -> str:
        return f"<WeeklyReport(id={self.id}, user_id={self.user_id}, week_start={self.week_start_date})>"
