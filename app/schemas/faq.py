"""
FAQ Pydantic Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.faq import FAQStatus


class FAQBase(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, example="How do I submit my Daily Work Report?")
    answer: str = Field(..., min_length=3, example="Navigate to Work Reports and click Submit Daily Report...")
    category: str = Field(default="Daily Operations", max_length=100)
    display_order: int = Field(default=0)
    status: FAQStatus = FAQStatus.PUBLISHED
    target_audience: str = Field(default="ALL")
    related_route: Optional[str] = Field(None, max_length=255)
    route_label: Optional[str] = Field(None, max_length=100)


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=3, max_length=500)
    answer: Optional[str] = Field(None, min_length=3)
    category: Optional[str] = Field(None, max_length=100)
    display_order: Optional[int] = None
    status: Optional[FAQStatus] = None
    target_audience: Optional[str] = None
    related_route: Optional[str] = None
    route_label: Optional[str] = None


class FAQResponse(FAQBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by_id: Optional[UUID] = None
    created_by_username: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class FAQListResponse(BaseModel):
    total: int
    items: List[FAQResponse]
