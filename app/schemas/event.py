"""
Events, Event Team, Readiness & Dashboard Pydantic Schemas
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.event import (
    EventMemberRole,
    EventMemberStatus,
    EventStatus,
    EventType,
    ReadinessCategory,
    ReadinessStatus,
)


class EventMemberBase(BaseModel):
    user_id: UUID
    role_in_event: EventMemberRole = EventMemberRole.COORDINATOR
    notes: Optional[str] = None


class EventMemberCreate(EventMemberBase):
    pass


class EventMemberUpdate(BaseModel):
    role_in_event: Optional[EventMemberRole] = None
    status: Optional[EventMemberStatus] = None
    notes: Optional[str] = None


class EventMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_in_event: EventMemberRole
    status: EventMemberStatus
    assigned_by_id: UUID
    assigned_at: datetime
    notes: Optional[str] = None


class EventReadinessItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    category: ReadinessCategory
    title: str
    description: Optional[str] = None
    status: ReadinessStatus
    assigned_user_id: Optional[UUID] = None
    assigned_username: Optional[str] = None
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[UUID] = None
    evidence_link: Optional[str] = None
    remarks: Optional[str] = None
    updated_at: datetime


class EventReadinessUpdate(BaseModel):
    status: ReadinessStatus
    assigned_user_id: Optional[UUID] = None
    deadline: Optional[datetime] = None
    evidence_link: Optional[str] = None
    remarks: Optional[str] = None


class EventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, example="Annual Inter-College Football Tournament")
    description: Optional[str] = None
    event_type: Optional[EventType] = EventType.TOURNAMENT
    planned_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    society_name: Optional[str] = None
    resource_links: Dict[str, Any] = Field(default_factory=dict)
    remarks: Optional[str] = None

    @field_validator("planned_date", mode="before")
    @classmethod
    def parse_planned_date(cls, v):
        if v == "" or v is None:
            return None
        return v

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_times(cls, v):
        if v == "" or v is None:
            return None
        return v


class EventPOCContact(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = Field(None, max_length=100)


class EventCreate(EventBase):
    vertical_id: UUID
    # External Event Team & Contacts (Phase 11)
    event_team_user_id: Optional[UUID] = None
    event_head_name: Optional[str] = None
    event_head_phone: Optional[str] = None
    event_head_email: Optional[str] = None
    additional_pocs: List[Dict[str, Any]] = Field(default_factory=list)
    # Internal User Account Selections (Phase 11 Standardized)
    poc_head_user_id: Optional[UUID] = None
    primary_poc_id: Optional[UUID] = None
    primary_poc_user_id: Optional[UUID] = None
    event_head_id: Optional[UUID] = None
    event_head_user_id: Optional[UUID] = None
    additional_poc_user_ids: List[UUID] = Field(default_factory=list)


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[EventType] = None
    planned_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    society_name: Optional[str] = None
    resource_links: Optional[Dict[str, Any]] = None
    remarks: Optional[str] = None


class EventTransitionRequest(BaseModel):
    status: EventStatus
    remarks: Optional[str] = None


class EventAssignPOCRequest(BaseModel):
    event_head_id: Optional[UUID] = None
    primary_poc_id: Optional[UUID] = None


class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vertical_id: UUID
    vertical_name: Optional[str] = None
    status: EventStatus
    event_head_id: Optional[UUID] = None
    event_head_username: Optional[str] = None
    primary_poc_id: Optional[UUID] = None
    primary_poc_username: Optional[str] = None
    event_team_user_id: Optional[UUID] = None
    event_team_username: Optional[str] = None
    event_team_name: Optional[str] = None
    created_by_id: UUID
    created_by_username: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseModel):
    total: int
    items: List[EventResponse]


class EventDashboardResponse(BaseModel):
    event: EventResponse
    team_members: List[EventMemberResponse]
    readiness_items: List[EventReadinessItemResponse]
    readiness_summary: Dict[str, int]
    tasks_count: int
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    requirements_count: int
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    meetings_count: int
    meetings: List[Dict[str, Any]] = Field(default_factory=list)
    issues_count: int
    issues: List[Dict[str, Any]] = Field(default_factory=list)


class POCMemberSummary(BaseModel):
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_in_event: EventMemberRole = EventMemberRole.POC
    status: EventMemberStatus = EventMemberStatus.ACTIVE
    notes: Optional[str] = None


class POCGroupAssignRequest(BaseModel):
    head_poc_id: UUID = Field(..., description="Designated Head POC for the Event (must be exactly 1 active Head POC)")
    poc_member_ids: List[UUID] = Field(default_factory=list, description="List of additional POC member user IDs")
    notes: Optional[str] = None


class POCGroupResponse(BaseModel):
    event_id: UUID
    event_name: str
    vertical_id: UUID
    head_poc: Optional[POCMemberSummary] = None
    poc_members: List[POCMemberSummary] = Field(default_factory=list)
    total_poc_count: int = 0
