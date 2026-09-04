"""
Meetings, Participants & Action Items Pydantic Schemas
Paradox Sports OMS - Phase 4 Event + Coordination System & Phase 1 Workspace Enhancements
"""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.meeting import MeetingStatus, MeetingType, RSVPStatus
from app.models.task import TaskPriority


class MeetingParticipantBase(BaseModel):
    user_id: UUID
    notes: Optional[str] = None


class MeetingParticipantCreate(MeetingParticipantBase):
    pass


class MeetingParticipantUpdate(BaseModel):
    rsvp_status: Optional[RSVPStatus] = None
    notes: Optional[str] = None


class MeetingRSVPRequest(BaseModel):
    rsvp_status: RSVPStatus
    notes: Optional[str] = None


class MeetingParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    meeting_id: UUID
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    rsvp_status: RSVPStatus
    invited_at: datetime
    responded_at: Optional[datetime] = None
    notes: Optional[str] = None


class MeetingActionItemCreate(BaseModel):
    description: str = Field(..., min_length=2, max_length=1000)
    assignee_id: Optional[UUID] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None


class MeetingActionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    meeting_id: UUID
    description: str
    assignee_id: Optional[UUID] = None
    assignee_username: Optional[str] = None
    assignee_full_name: Optional[str] = None
    priority: TaskPriority
    due_date: Optional[datetime] = None
    is_converted: bool
    converted_task_id: Optional[UUID] = None
    converted_at: Optional[datetime] = None
    converted_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class MeetingActionConvertToTaskRequest(BaseModel):
    vertical_id: Optional[UUID] = None  # If not provided, inherits from meeting
    assigned_to_id: Optional[UUID] = None  # If not provided, inherits from action item assignee
    title: Optional[str] = Field(None, max_length=255)  # If not provided, derived from action item description
    priority: Optional[TaskPriority] = None
    deadline: Optional[datetime] = None


class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, example="Pre-Match Coordination Briefing")
    description: Optional[str] = None
    meeting_type: MeetingType = MeetingType.INTERNAL_SYNC
    meeting_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    remarks: Optional[str] = None


class MeetingCreate(MeetingBase):
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    participant_ids: List[UUID] = Field(default_factory=list)
    # Hierarchical Group Audience Support (Phase 10E)
    include_all_organization: bool = False
    target_vertical_ids: List[UUID] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_role_vertical_pairs: List[dict] = Field(default_factory=list)


class MeetingRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, example="Team Sync Request")
    description: Optional[str] = None
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    meeting_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    remarks: Optional[str] = None
    participant_ids: List[UUID] = Field(default_factory=list)


class MeetingReviewRequest(BaseModel):
    status: MeetingStatus = MeetingStatus.SCHEDULED  # SCHEDULED (Approved) or REJECTED
    remarks: Optional[str] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    meeting_type: Optional[MeetingType] = None
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    remarks: Optional[str] = None


class MeetingRescheduleRequest(BaseModel):
    meeting_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    remarks: Optional[str] = None


class MeetingResponse(MeetingBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organizer_id: UUID
    organizer_username: Optional[str] = None
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    status: MeetingStatus

    # Request workflow tracking
    is_requested: bool = False
    requested_by_id: Optional[UUID] = None
    requested_by_username: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    participants: List[MeetingParticipantResponse] = Field(default_factory=list)
    action_items: List[MeetingActionItemResponse] = Field(default_factory=list)


class MeetingListResponse(BaseModel):
    total: int
    items: List[MeetingResponse]
