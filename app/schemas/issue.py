"""
Pydantic Schemas for Issue & Escalation Register
Paradox Sports OMS - Phase 3 Core Operational System
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.issue import IssueSensitivity, IssueStatus


class IssueCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class IssueCommentResponse(BaseModel):
    id: UUID
    issue_id: UUID
    author_id: UUID
    author_username: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueHistoryResponse(BaseModel):
    id: UUID
    issue_id: UUID
    actor_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    action: str
    details: Optional[dict] = None
    timestamp: datetime
    correlation_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IssueAssigneeSummary(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=5)

    # Audience / Scope
    vertical_id: Optional[UUID] = None
    vertical_ids: Optional[List[UUID]] = None
    all_users: Optional[bool] = False

    # Assignee / Responsible Users
    assigned_to_id: Optional[UUID] = None
    assignee_user_ids: Optional[List[UUID]] = None
    assignee_role_ids: Optional[List[str]] = None
    assignee_vertical_ids: Optional[List[UUID]] = None
    assignee_all_users: Optional[bool] = False

    sensitivity: IssueSensitivity = IssueSensitivity.NORMAL
    action_required: Optional[str] = None
    deadline: Optional[datetime] = None
    evidence_link: Optional[str] = None
    event_reference: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator(
        "vertical_id",
        "assigned_to_id",
        "action_required",
        "deadline",
        "evidence_link",
        "event_reference",
        "remarks",
        mode="before",
    )
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    event_reference: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    assignee_user_ids: Optional[List[UUID]] = None
    sensitivity: Optional[IssueSensitivity] = None
    action_required: Optional[str] = None
    deadline: Optional[datetime] = None
    evidence_link: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator(
        "assigned_to_id",
        "action_required",
        "deadline",
        "evidence_link",
        "event_reference",
        "remarks",
        mode="before",
    )
    @classmethod
    def coerce_empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class IssueTransitionRequest(BaseModel):
    status: IssueStatus
    resolution: Optional[str] = None
    remarks: Optional[str] = None


class IssueEscalateRequest(BaseModel):
    escalation_target: str = Field(..., min_length=2, max_length=255)
    escalation_action: str = Field(..., min_length=5)
    deadline: Optional[datetime] = None
    remarks: Optional[str] = None


class IssueResponse(BaseModel):
    id: UUID
    date_raised: datetime
    vertical_id: UUID
    vertical_name: Optional[str] = None
    event_reference: Optional[str] = None
    title: str
    description: str
    raised_by_id: UUID
    raised_by_username: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    assigned_to_username: Optional[str] = None
    assignee_ids: List[UUID] = Field(default_factory=list)
    assignees: List[IssueAssigneeSummary] = Field(default_factory=list)
    sensitivity: IssueSensitivity
    status: IssueStatus
    action_required: Optional[str] = None
    deadline: Optional[datetime] = None
    escalation_target: Optional[str] = None
    escalation_action: Optional[str] = None
    resolution: Optional[str] = None
    resolution_date: Optional[datetime] = None
    evidence_link: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    total: int
    items: List[IssueResponse]
