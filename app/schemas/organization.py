"""
Organization and Vertical Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.organization import VerticalStatus


class VerticalBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, example="Football Operations")
    description: Optional[str] = Field(None, max_length=2000)


class VerticalCreate(VerticalBase):
    organization_id: Optional[UUID] = None


class VerticalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[VerticalStatus] = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if isinstance(v, str) and v.upper() == "INACTIVE":
            return VerticalStatus.DISABLED
        return v


class VerticalResponse(VerticalBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    status: VerticalStatus
    created_at: datetime
    updated_at: datetime


class VerticalListResponse(BaseModel):
    total: int
    items: List[VerticalResponse]


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    verticals: List[VerticalResponse] = Field(default_factory=list)


class AssignVerticalItem(BaseModel):
    vertical_id: UUID
    is_primary: bool = False


class AssignVerticalsRequest(BaseModel):
    assignments: List[AssignVerticalItem]


class SelectorItem(BaseModel):
    id: str
    type: str  # USER, MULTI_USER, VERTICAL, ROLE, ROLE_VERTICAL, EVENT_TEAM, ALL_USERS, GROUP
    label: str
    sublabel: Optional[str] = None
    badge: Optional[str] = None
    member_count: Optional[int] = None
    metadata: Optional[dict] = Field(default_factory=dict)


class SelectorGroupItem(BaseModel):
    type: str  # vertical, role, role_vertical, organization, event_team
    id: str
    name: str
    member_count: int
    vertical_id: Optional[str] = None
    role: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)


class SelectorUserItem(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[dict] = None
    vertical: Optional[dict] = None
    account_status: Optional[str] = None


class SelectorResponse(BaseModel):
    selection_type: str
    total: int
    items: List[SelectorItem] = Field(default_factory=list)
    groups: Optional[List[SelectorGroupItem]] = Field(default_factory=list)
    users: Optional[List[SelectorUserItem]] = Field(default_factory=list)


class AudienceResolveRequest(BaseModel):
    all_users: bool = False
    vertical_ids: List[UUID] = Field(default_factory=list)
    role_ids: List[str] = Field(default_factory=list)
    user_ids: List[UUID] = Field(default_factory=list)
    event_id: Optional[UUID] = None
    usage: str = "audience"
    union_groups: bool = False


class ResolvedUserSummary(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    account_status: str
    roles: List[str] = Field(default_factory=list)
    verticals: List[str] = Field(default_factory=list)


class AudienceResolveResponse(BaseModel):
    total_count: int
    user_ids: List[UUID] = Field(default_factory=list)
    users: List[ResolvedUserSummary] = Field(default_factory=list)
    audience_summary: str
    is_all_users: bool = False


