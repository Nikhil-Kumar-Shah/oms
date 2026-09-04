"""
RBAC & Permissions Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: Optional[str] = None
    category: str


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool
    permissions: List[PermissionResponse] = Field(default_factory=list)


class AssignRolesRequest(BaseModel):
    role_ids: List[UUID] = Field(..., description="List of Role UUIDs to assign to user")


class PermissionOverrideItem(BaseModel):
    permission_id: UUID
    is_granted: bool = Field(..., description="True for explicit grant, False for explicit revoke")


class SetPermissionOverridesRequest(BaseModel):
    overrides: List[PermissionOverrideItem]
