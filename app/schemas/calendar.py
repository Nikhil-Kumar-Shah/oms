"""
Pydantic Schemas for Master Calendar
Paradox Sports OMS - Phase 3 Core Operational System & Phase 1 Workspace Enhancements
"""

from datetime import date, datetime, time
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.calendar import (
    ActivityCategory,
    CalendarAudience,
    CalendarPriority,
    CalendarStatus,
    DeadlineType,
    RecurrenceFrequency,
)


class CalendarCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    activity_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    category: ActivityCategory = ActivityCategory.ACTIVITY
    priority: CalendarPriority = CalendarPriority.MEDIUM
    status: CalendarStatus = CalendarStatus.PLANNED
    deadline_type: DeadlineType = DeadlineType.INFORMATIONAL
    audience: Optional[CalendarAudience] = None
    vertical_id: Optional[UUID] = None
    event_reference: Optional[str] = None
    resource_link: Optional[str] = None
    remarks: Optional[str] = None

    # Universal Audience & Personal Activity flags
    is_personal: bool = False
    user_ids: Optional[List[UUID]] = None
    vertical_ids: Optional[List[UUID]] = None
    role_ids: Optional[List[str]] = None
    all_users: Optional[bool] = None

    # Recurrence & Entity Links
    recurrence: RecurrenceFrequency = RecurrenceFrequency.NONE
    recurrence_end_date: Optional[date] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    requirement_id: Optional[UUID] = None

    @field_validator(
        "description",
        "event_reference",
        "resource_link",
        "remarks",
        "entity_type",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class CalendarUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    activity_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    category: Optional[ActivityCategory] = None
    priority: Optional[CalendarPriority] = None
    status: Optional[CalendarStatus] = None
    deadline_type: Optional[DeadlineType] = None
    audience: Optional[CalendarAudience] = None
    vertical_id: Optional[UUID] = None
    event_reference: Optional[str] = None
    resource_link: Optional[str] = None
    remarks: Optional[str] = None

    # Recurrence & Links
    recurrence: Optional[RecurrenceFrequency] = None
    recurrence_end_date: Optional[date] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    requirement_id: Optional[UUID] = None

    @field_validator(
        "title",
        "description",
        "event_reference",
        "resource_link",
        "remarks",
        "entity_type",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class CalendarResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    activity_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    category: ActivityCategory
    priority: CalendarPriority
    status: CalendarStatus
    deadline_type: DeadlineType
    audience: CalendarAudience
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    event_reference: Optional[str] = None
    resource_link: Optional[str] = None
    remarks: Optional[str] = None
    recurrence: RecurrenceFrequency = RecurrenceFrequency.NONE
    recurrence_end_date: Optional[date] = None
    entity_type: Optional[str] = "CALENDAR_ENTRY"
    entity_id: Optional[UUID] = None
    is_personal: bool = False
    task_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    requirement_id: Optional[UUID] = None
    created_by_id: UUID
    created_by_username: Optional[str] = None
    target_user_ids: Optional[List[UUID]] = None
    created_at: datetime
    # Reschedule and individual completion tracking
    original_date: Optional[date] = None
    rescheduled_at: Optional[datetime] = None
    is_user_completed: Optional[bool] = False
    user_completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CalendarActionRequest(BaseModel):
    action: str = Field(..., description="Action: 'complete', 'in_progress', 'cancel', 'mark_completed_for_me'")
    remarks: Optional[str] = None


class CalendarRescheduleRequest(BaseModel):
    new_date: date
    new_start_time: Optional[time] = None
    new_end_time: Optional[time] = None
    reason: Optional[str] = None


class CalendarListResponse(BaseModel):
    total: int
    items: List[CalendarResponse]

