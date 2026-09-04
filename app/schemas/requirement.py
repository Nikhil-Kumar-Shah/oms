"""
Cross-Vertical Requirements & Messages Pydantic Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.requirement import RequirementPriority, RequirementStatus


class RequirementMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, example="Pitch preparation equipment dispatched.")


class RequirementMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requirement_id: UUID
    author_id: UUID
    author_username: Optional[str] = None
    author_full_name: Optional[str] = None
    content: str
    created_at: datetime


class RequirementBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, example="Request 4 Goal Net Sets for Field B")
    description: str = Field(..., min_length=1, max_length=5000)
    priority: RequirementPriority = RequirementPriority.MEDIUM
    deadline: Optional[datetime] = None
    remarks: Optional[str] = None
    reference_link: Optional[str] = Field(None, max_length=1024, description="Optional reference link (Google Drive, doc, asset, etc.)")


class RequirementCreate(RequirementBase):
    requesting_vertical_id: Optional[UUID] = None
    target_vertical_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    event_id: Optional[UUID] = None


class RequirementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1, max_length=5000)
    priority: Optional[RequirementPriority] = None
    deadline: Optional[datetime] = None
    remarks: Optional[str] = None


class RequirementAssignRequest(BaseModel):
    assignee_id: Optional[UUID] = None


class RequirementForwardRequest(BaseModel):
    target_user_id: Optional[UUID] = Field(None, description="Target user / POC UUID")
    target_vertical_id: Optional[UUID] = Field(None, description="Target vertical UUID if forwarding to vertical")
    reason: str = Field(..., min_length=2, max_length=2000, description="Reason for forwarding internally")


class RequirementEscalateRequest(BaseModel):
    escalated_to_id: UUID = Field(..., description="Target authority/supervisor user UUID")
    reason: str = Field(..., min_length=2, max_length=2000, description="Detailed rationale for escalation")


class RequirementResolveEscalationRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=2, max_length=2000, description="Notes detailing how the escalation was resolved")


class RequirementTransitionRequest(BaseModel):
    status: RequirementStatus
    remarks: Optional[str] = None


class RequirementResponse(RequirementBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    responsible_poc_id: Optional[UUID] = None
    responsible_poc_username: Optional[str] = None
    responsible_poc_full_name: Optional[str] = None
    requesting_vertical_id: Optional[UUID] = None
    requesting_vertical_name: Optional[str] = None
    target_vertical_id: Optional[UUID] = None
    target_vertical_name: Optional[str] = None
    requester_id: UUID
    requester_username: Optional[str] = None
    requester_full_name: Optional[str] = None
    assignee_id: Optional[UUID] = None
    assignee_username: Optional[str] = None
    assignee_full_name: Optional[str] = None
    status: RequirementStatus
    forward_history: List[Dict[str, Any]] = []

    # Escalation fields
    is_escalated: bool = False
    escalated_to_id: Optional[UUID] = None
    escalated_to_username: Optional[str] = None
    escalated_to_full_name: Optional[str] = None
    escalated_by_id: Optional[UUID] = None
    escalated_by_username: Optional[str] = None
    escalated_by_full_name: Optional[str] = None
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None
    escalation_status: Optional[str] = None
    escalation_resolved_at: Optional[datetime] = None
    escalation_resolved_by_id: Optional[UUID] = None
    escalation_resolution_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    messages_count: int = 0


class RequirementListResponse(BaseModel):
    total: int
    items: List[RequirementResponse]
