"""
Pydantic Schemas for Unified Operational Workspace & My Work
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.calendar import ActivityCategory, CalendarPriority
from app.models.communication import DirectivePriority
from app.models.event import EventMemberRole, EventStatus, EventType
from app.models.meeting import MeetingStatus, MeetingType, RSVPStatus
from app.models.task import TaskHealth, TaskPriority, TaskStatus, TaskType


class MyWorkTaskItem(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    vertical_id: UUID
    vertical_name: Optional[str] = None
    task_type: TaskType = TaskType.ROUTINE
    priority: TaskPriority
    status: TaskStatus
    health: TaskHealth
    progress_percentage: int
    deadline: Optional[datetime] = None
    blocker_reason: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    assigned_to_username: Optional[str] = None
    assigned_by_id: Optional[UUID] = None
    assigned_by_name: Optional[str] = None
    assigned_by_username: Optional[str] = None
    event_id: Optional[UUID] = None
    event_title: Optional[str] = None
    created_at: datetime


class MyWorkDirectiveItem(BaseModel):
    id: UUID
    directive_id: UUID
    title: str
    summary: str
    priority: DirectivePriority
    issued_by_name: Optional[str] = None
    deadline: Optional[datetime] = None
    issued_at: datetime


class MyWorkMeetingItem(BaseModel):
    id: UUID
    title: str
    meeting_type: MeetingType
    meeting_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    rsvp_status: RSVPStatus
    organizer_name: Optional[str] = None


class MyWorkEventDutyItem(BaseModel):
    event_id: UUID
    title: str
    event_type: EventType
    event_status: EventStatus
    planned_date: date
    role: EventMemberRole
    location: Optional[str] = None


class MyWorkFormItem(BaseModel):
    id: UUID
    form_id: UUID
    form_title: str
    purpose: str
    category: Optional[str] = "Operational"
    status: str
    deadline: Optional[datetime] = None
    vertical_name: Optional[str] = None
    instructions: Optional[str] = None
    created_at: Optional[datetime] = None


class MyWorkReviewItem(BaseModel):
    id: UUID
    item_type: str  # 'FORM_REVIEW' | 'TRANSFER_APPROVAL'
    title: str
    submitted_by_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: str
    urgency: str = "NORMAL"  # 'NORMAL' | 'HIGH' | 'CRITICAL'
    target_entity_id: Optional[UUID] = None
    link: str


class MyWorkIssueItem(BaseModel):
    id: UUID
    title: str
    status: str
    sensitivity: str
    vertical_name: Optional[str] = None
    event_reference: Optional[str] = None
    raised_by_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    deadline: Optional[datetime] = None
    escalation_target: Optional[str] = None
    action_required: Optional[str] = None
    created_at: datetime


class MyWorkPriorityItem(BaseModel):
    id: str
    item_type: str  # 'TASK' | 'ISSUE' | 'FORM' | 'REVIEW' | 'APPROVAL'
    title: str
    urgency: str  # 'OVERDUE' | 'CRITICAL' | 'APPROVAL_NEEDED' | 'DEADLINE_SOON' | 'ACTION_REQUIRED'
    urgency_label: str
    due_date: Optional[datetime] = None
    detail: Optional[str] = None
    action_link: str
    action_label: str


class MyWorkUserContext(BaseModel):
    primary_role: str
    operational_level: Optional[int] = None
    responsibilities: List[str] = Field(default_factory=list)
    verticals: List[str] = Field(default_factory=list)
    event_team_profile: Optional[dict] = None
    attention_summary: str = ""
    requires_immediate_attention: bool = False


class MyWorkStats(BaseModel):
    active_tasks: int
    completed_tasks: int = 0
    created_by_me_tasks: int = 0
    pending_directives: int = 0
    upcoming_meetings: int = 0
    event_duties: int = 0
    blocked_tasks: int = 0
    overdue_tasks: int = 0
    active_issues: int = 0
    pending_forms: int = 0
    pending_reviews: int = 0
    pending_approvals: int = 0


class UnifiedMyWorkResponse(BaseModel):
    user_id: UUID
    username: str
    full_name: str
    context: Optional[MyWorkUserContext] = None
    stats: MyWorkStats
    priority_queue: List[MyWorkPriorityItem] = Field(default_factory=list)
    tasks: List[MyWorkTaskItem] = Field(default_factory=list)
    completed_tasks: List[MyWorkTaskItem] = Field(default_factory=list)
    created_by_me_tasks: List[MyWorkTaskItem] = Field(default_factory=list)
    pending_forms: List[MyWorkFormItem] = Field(default_factory=list)
    pending_reviews: List[MyWorkReviewItem] = Field(default_factory=list)
    active_issues: List[MyWorkIssueItem] = Field(default_factory=list)
    pending_directives: List[MyWorkDirectiveItem] = Field(default_factory=list)
    meetings: List[MyWorkMeetingItem] = Field(default_factory=list)
    event_duties: List[MyWorkEventDutyItem] = Field(default_factory=list)
    blockers: List[MyWorkTaskItem] = Field(default_factory=list)
    overdue: List[MyWorkTaskItem] = Field(default_factory=list)
