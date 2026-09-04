"""
Pydantic Schemas for Daily & Weekly Work Reports & Weekly Rollup
Paradox Sports OMS - Phase 3 Core Operational System & Phase 10J Review Hierarchy
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.report import DailyReportStatus, WeeklyReportStatus


class DailyReportTaskCreate(BaseModel):
    task_id: UUID
    progress_notes: Optional[str] = None

    @field_validator("progress_notes", mode="before")
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class DailyReportTaskResponse(BaseModel):
    task_id: UUID
    task_title: Optional[str] = None
    task_status: Optional[str] = None
    progress_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DailyReportHistoryResponse(BaseModel):
    id: UUID
    report_id: UUID
    actor_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    action: str
    comments: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyReportCreate(BaseModel):
    vertical_id: Optional[UUID] = None
    report_date: Optional[date] = None
    work_summary: str = Field(..., min_length=5)
    tasks: Optional[List[DailyReportTaskCreate]] = Field(default_factory=list)
    task_ids: Optional[List[UUID]] = Field(default_factory=list)
    assigned_task_id: Optional[UUID] = None  # backward compatibility
    tasks_completed: Optional[str] = None
    blockers: Optional[str] = None
    issues: Optional[str] = None
    next_actions: Optional[str] = None
    evidence_links: Optional[str] = None
    submit_now: bool = True

    @field_validator(
        "vertical_id",
        "report_date",
        "assigned_task_id",
        "tasks_completed",
        "blockers",
        "issues",
        "next_actions",
        "evidence_links",
        mode="before",
    )
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class DailyReportUpdate(BaseModel):
    work_summary: Optional[str] = Field(None, min_length=5)
    tasks: Optional[List[DailyReportTaskCreate]] = None
    task_ids: Optional[List[UUID]] = None
    tasks_completed: Optional[str] = None
    blockers: Optional[str] = None
    issues: Optional[str] = None
    next_actions: Optional[str] = None
    evidence_links: Optional[str] = None
    submit_now: Optional[bool] = None

    @field_validator(
        "tasks_completed",
        "blockers",
        "issues",
        "next_actions",
        "evidence_links",
        mode="before",
    )
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class DailyReportReviewRequest(BaseModel):
    status: DailyReportStatus  # REVIEWED, RETURNED, FLAGGED
    review_comments: Optional[str] = None

    @field_validator("review_comments", mode="before")
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class DailyReportResponse(BaseModel):
    id: UUID
    user_id: UUID
    author_id: Optional[UUID] = None
    user_role: Optional[str] = None
    username: Optional[str] = None
    user_full_name: Optional[str] = None
    vertical_id: UUID
    vertical_name: Optional[str] = None
    report_date: date
    work_summary: str
    tasks_completed: Optional[str] = None
    tasks: List[DailyReportTaskResponse] = Field(default_factory=list)
    blockers: Optional[str] = None
    issues: Optional[str] = None
    next_actions: Optional[str] = None
    evidence_links: Optional[str] = None
    status: DailyReportStatus
    reviewer_id: Optional[UUID] = None
    reviewer_username: Optional[str] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_by_username: Optional[str] = None
    review_comments: Optional[str] = None
    history: List[DailyReportHistoryResponse] = Field(default_factory=list)
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyReportListResponse(BaseModel):
    total: int
    items: List[DailyReportResponse]


# Dynamic Weekly Rollup Models
class WeeklyTaskSummary(BaseModel):
    id: UUID
    title: str
    status: str
    priority: str
    assigned_to_name: Optional[str] = None
    deadline: Optional[datetime] = None


class WeeklyIssueSummary(BaseModel):
    id: UUID
    title: str
    status: str
    sensitivity: str


class WeeklyRollupResponse(BaseModel):
    start_date: date
    end_date: date
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    daily_reports_count: int
    daily_reports_submitted: List[DailyReportResponse] = Field(default_factory=list)
    completed_tasks_count: int
    completed_tasks: List[WeeklyTaskSummary] = Field(default_factory=list)
    incomplete_tasks_count: int
    incomplete_tasks: List[WeeklyTaskSummary] = Field(default_factory=list)
    blockers_count: int
    blockers: List[str] = Field(default_factory=list)
    major_issues_count: int
    major_issues: List[WeeklyIssueSummary] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    existing_weekly_report: Optional["WeeklyReportResponse"] = None


class WeeklyReportCreate(BaseModel):
    vertical_id: Optional[UUID] = None
    week_start_date: date
    week_end_date: date
    summary: str = Field(..., min_length=5)
    completed_work: Optional[str] = None
    outstanding_work: Optional[str] = None
    blockers: Optional[str] = None
    issues: Optional[str] = None
    priorities_next_week: Optional[str] = None
    submit_now: bool = True

    @field_validator(
        "vertical_id",
        "completed_work",
        "outstanding_work",
        "blockers",
        "issues",
        "priorities_next_week",
        mode="before",
    )
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class WeeklyReportReviewRequest(BaseModel):
    status: WeeklyReportStatus  # REVIEWED, RETURNED
    supervisor_comments: Optional[str] = None

    @field_validator("supervisor_comments", mode="before")
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class WeeklyReportResponse(BaseModel):
    id: UUID
    user_id: UUID
    author_id: Optional[UUID] = None
    user_role: Optional[str] = None
    username: Optional[str] = None
    user_full_name: Optional[str] = None
    vertical_id: UUID
    vertical_name: Optional[str] = None
    week_start_date: date
    week_end_date: date
    days_reported_count: int = 0
    days_reported: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str
    completed_work: Optional[str] = None
    outstanding_work: Optional[str] = None
    tasks_worked_on: List[DailyReportTaskResponse] = Field(default_factory=list)
    daily_reports: List[DailyReportResponse] = Field(default_factory=list)
    blockers: Optional[str] = None
    issues: Optional[str] = None
    priorities_next_week: Optional[str] = None
    supervisor_comments: Optional[str] = None
    reviewer_id: Optional[UUID] = None
    reviewer_username: Optional[str] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_by_username: Optional[str] = None
    status: WeeklyReportStatus
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyReportListResponse(BaseModel):
    total: int
    items: List[WeeklyReportResponse]
