"""
Governance Schemas
Includes Resource Ownership Transfers and System Configuration Schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.governance import (
    ConfigValueType,
    TransferResourceType,
    TransferStatus,
)


# -----------------------------------------------------------------------------
# Ownership Transfer & Account Succession Schemas
# -----------------------------------------------------------------------------

class OwnershipTransferCreate(BaseModel):
    resource_type: TransferResourceType
    resource_id: UUID
    requested_owner_id: UUID
    reason: str = Field(..., min_length=5)


class SuccessionUserSummary(BaseModel):
    id: UUID
    username: str
    full_name: str
    email: Optional[str] = None
    account_status: str
    role_name: Optional[str] = None


class SuccessionTaskSummary(BaseModel):
    id: UUID
    title: str
    priority: str
    status: str
    vertical_name: Optional[str] = None


class SuccessionEventSummary(BaseModel):
    id: UUID
    name: str
    status: str
    role: str


class SuccessionVerticalSummary(BaseModel):
    id: UUID
    name: str
    is_primary: bool


class AccountSuccessionPreviewResponse(BaseModel):
    previous_user: SuccessionUserSummary
    successor_user: SuccessionUserSummary
    active_tasks_count: int
    active_tasks: List[SuccessionTaskSummary] = Field(default_factory=list)
    active_events_count: int
    active_events: List[SuccessionEventSummary] = Field(default_factory=list)
    active_requirements_count: int
    assigned_verticals: List[SuccessionVerticalSummary] = Field(default_factory=list)
    historical_preservation_note: str = (
        "Historical completed tasks, submitted reports, meetings, past communications, "
        "and audit logs will remain permanently preserved under the Previous Account."
    )


class AccountSuccessionCreate(BaseModel):
    previous_user_id: UUID
    successor_user_id: UUID
    reason: str = Field(..., min_length=5, description="Administrative justification for account succession")


class OwnershipTransferReviewRequest(BaseModel):
    status: TransferStatus = Field(..., description="Must be APPROVED or REJECTED")
    remarks: Optional[str] = None


class OwnershipTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_type: TransferResourceType
    resource_id: UUID
    resource_name: Optional[str] = None
    current_owner_id: UUID
    current_owner_username: Optional[str] = None
    requested_owner_id: UUID
    requested_owner_username: Optional[str] = None
    requested_by_id: UUID
    requested_by_username: Optional[str] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_by_username: Optional[str] = None
    reason: str
    status: TransferStatus
    remarks: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OwnershipTransferListResponse(BaseModel):
    total: int
    items: List[OwnershipTransferResponse]


# -----------------------------------------------------------------------------
# System Configuration Schemas
# -----------------------------------------------------------------------------

class SystemConfigCreate(BaseModel):
    key: str = Field(..., min_length=2, max_length=100)
    value: str = Field(...)
    value_type: ConfigValueType = ConfigValueType.STRING
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class SystemConfigUpdate(BaseModel):
    value: str = Field(...)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class SystemConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    value: str
    value_type: ConfigValueType
    description: Optional[str] = None
    is_active: bool
    updated_by_id: Optional[UUID] = None
    updated_by_username: Optional[str] = None
    updated_at: datetime


class SystemConfigListResponse(BaseModel):
    total: int
    items: List[SystemConfigResponse]
