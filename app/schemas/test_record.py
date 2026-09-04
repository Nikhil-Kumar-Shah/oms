"""
Pydantic Schemas for SystemTestRecord
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SystemTestRecordBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the test record")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description")


class SystemTestRecordCreate(SystemTestRecordBase):
    pass


class SystemTestRecordUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class SystemTestRecordResponse(SystemTestRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class SystemTestRecordListResponse(BaseModel):
    total: int = Field(..., example=1)
    items: List[SystemTestRecordResponse]
