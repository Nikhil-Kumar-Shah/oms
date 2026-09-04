"""
User Management Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import AccountStatus


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role_ids: Optional[List[UUID]] = Field(default_factory=list)
    vertical_ids: Optional[List[UUID]] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)


class UserResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserRoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class UserVerticalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_primary: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    full_name: str
    email: Optional[str] = None
    account_status: AccountStatus
    roles: List[UserRoleSummary] = Field(default_factory=list)
    verticals: List[UserVerticalSummary] = Field(default_factory=list)
    last_login_at: Optional[datetime] = None
    disabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    total: int
    items: List[UserResponse]
