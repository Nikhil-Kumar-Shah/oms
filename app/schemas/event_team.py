"""
Event Team Account & Operational Profile Schemas
Paradox Sports OMS - Phase 1 Organization + People + Role Governance
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class EventTeamCredentialsCreate(BaseModel):
    """Payload for Admin creating Event Team account credentials (unactivated)."""
    username: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(None, max_length=255)
    team_name: Optional[str] = Field(None, max_length=255)


class EventTeamActivate(BaseModel):
    """
    Payload for Sports Core / Deputy Core activating an Event Team.
    Contains ONLY:
    - Event Team Name
    - Event Head Name
    - Event Head Phone Number
    - Event Head Email
    - Select Event Team Account (user_id)
    - Head POC (head_poc_id)
    - Additional POCs (additional_poc_ids)
    """
    team_name: str = Field(..., min_length=1, max_length=255)
    head_name: str = Field(..., min_length=1, max_length=255)
    head_phone: str = Field(..., min_length=1, max_length=50)
    head_email: str = Field(..., min_length=1, max_length=255)
    user_id: UUID = Field(..., description="The Event Team Account created by Admin")
    head_poc_id: UUID = Field(..., description="Head POC selected via Universal Selector")
    additional_poc_ids: List[UUID] = Field(default_factory=list, description="Additional POCs selected via Universal Selector")
    event_id: UUID = Field(..., description="The Event to assign this Event Team to")
    notes: Optional[str] = None


class UnactivatedAccountResponse(BaseModel):
    """Summary of unactivated Event Team account ready for activation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    account_status: str
    created_at: datetime


class EventTeamCreate(BaseModel):
    """Payload for creating an Event Team user account and related profile."""
    username: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=255)
    event_id: Optional[UUID] = None
    team_name: Optional[str] = Field(None, max_length=255)
    head_name: Optional[str] = Field(None, max_length=255)
    head_email: Optional[str] = Field(None, max_length=255)
    head_phone: Optional[str] = Field(None, max_length=50)
    members_summary: List[Dict[str, Any]] = Field(default_factory=list)
    contact_info: Dict[str, Any] = Field(default_factory=dict)
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    is_activated: Optional[bool] = Field(default=None, description="Initial activation status (defaults to False if unassigned)")


class EventTeamUpdate(BaseModel):
    """Payload for updating an Event Team operational profile."""
    event_id: Optional[UUID] = None
    team_name: Optional[str] = Field(None, min_length=1, max_length=255)
    head_name: Optional[str] = Field(None, max_length=255)
    head_email: Optional[str] = Field(None, max_length=255)
    head_phone: Optional[str] = Field(None, max_length=50)
    members_summary: Optional[List[Dict[str, Any]]] = None
    contact_info: Optional[Dict[str, Any]] = None
    event_metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EventTeamProfileResponse(BaseModel):
    """Structured Event Team profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    username: Optional[str] = None
    account_status: Optional[str] = None
    is_activated: bool = False
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_status: Optional[str] = None
    team_name: str
    head_name: Optional[str] = None
    head_email: Optional[str] = None
    head_phone: Optional[str] = None
    head_poc_id: Optional[UUID] = None
    head_poc_name: Optional[str] = None
    head_poc_username: Optional[str] = None
    additional_pocs: List[Dict[str, Any]] = Field(default_factory=list)
    members_summary: List[Dict[str, Any]] = Field(default_factory=list)
    contact_info: Dict[str, Any] = Field(default_factory=dict)
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    # Meaningful operational activity counts
    requirements_count: int = 0
    issues_count: int = 0
    meetings_count: int = 0
    members_count: int = 0

    created_at: datetime
    updated_at: datetime


class EventTeamListResponse(BaseModel):
    """Paginated or listed Event Teams response."""
    total: int
    items: List[EventTeamProfileResponse]
