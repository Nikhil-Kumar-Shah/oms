"""
Authentication & Session Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.user import AccountStatus


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255, description="Username or registered email address", example="admin")
    password: str = Field(..., min_length=1, max_length=128, example="AdminPassword@123")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class SessionInfo(BaseModel):
    session_id: UUID
    token: str
    expires_at: datetime


class UserRoleInfo(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None


class UserVerticalInfo(BaseModel):
    id: UUID
    name: str
    is_primary: bool


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: Optional[str] = None
    full_name: str
    account_status: AccountStatus
    roles: List[UserRoleInfo]
    effective_permissions: List[str]
    verticals: List[UserVerticalInfo]
    last_login_at: Optional[datetime] = None


class AuthSuccessResponse(BaseModel):
    success: bool = True
    session: SessionInfo
    user: MeResponse
