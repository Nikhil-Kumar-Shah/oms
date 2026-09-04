"""
Pydantic Schemas for User & Team Profile Metadata
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.user import UserAvailability


class UserProfileBase(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=50)
    specialization: Optional[str] = Field(None, max_length=255, example="Football Referee, Match Operations")
    operational_capability: Optional[str] = Field(None, example="Ground setup, electronic scorekeeping, pitch certification")
    certifications: List[str] = Field(default_factory=list, example=["FIFA Grassroots Referee", "Red Cross CPR"])
    availability: UserAvailability = UserAvailability.AVAILABLE
    profile_notes: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=50)
    specialization: Optional[str] = Field(None, max_length=255)
    operational_capability: Optional[str] = None
    certifications: Optional[List[str]] = None
    availability: Optional[UserAvailability] = None
    profile_notes: Optional[str] = None


class UserProfileResponse(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    account_created_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
