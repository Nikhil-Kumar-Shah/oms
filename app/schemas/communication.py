"""
Communication Schemas
Includes schemas for Announcements, Directives, Acknowledgements, Notifications, and Communication Logs.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.communication import (
    AcknowledgementStatus,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    CommunicationLogStatus,
    CommunicationType,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
    NotificationReadStatus,
    NotificationType,
)


# -----------------------------------------------------------------------------
# Announcements Schemas
# -----------------------------------------------------------------------------

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=5)
    category: str = Field("GENERAL", max_length=50)
    priority: AnnouncementPriority = AnnouncementPriority.NORMAL
    scope: AnnouncementScope = AnnouncementScope.ALL
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    target_user_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None
    publish_now: bool = False


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=5)
    category: Optional[str] = Field(None, max_length=50)
    priority: Optional[AnnouncementPriority] = None
    scope: Optional[AnnouncementScope] = None
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    target_user_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    category: str
    priority: AnnouncementPriority
    scope: AnnouncementScope
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    target_user_id: Optional[UUID] = None
    target_username: Optional[str] = None
    author_id: UUID
    author_username: Optional[str] = None
    status: AnnouncementStatus
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AnnouncementListResponse(BaseModel):
    total: int
    items: List[AnnouncementResponse]


# -----------------------------------------------------------------------------
# Directives Schemas
# -----------------------------------------------------------------------------

class DirectiveCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    instruction: str = Field(..., min_length=5)
    scope: DirectiveScope = DirectiveScope.ALL
    vertical_id: Optional[UUID] = None
    target_user_id: Optional[UUID] = None
    priority: DirectivePriority = DirectivePriority.MEDIUM
    effective_date: date = Field(default_factory=date.today)
    deadline: Optional[date] = None
    requires_acknowledgement: bool = True
    issue_now: bool = False


class DirectiveUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    instruction: Optional[str] = Field(None, min_length=5)
    priority: Optional[DirectivePriority] = None
    effective_date: Optional[date] = None
    deadline: Optional[date] = None
    requires_acknowledgement: Optional[bool] = None


class DirectiveAcknowledgementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    directive_id: UUID
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    status: AcknowledgementStatus
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class DirectiveAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class DirectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    instruction: str
    issued_by_id: UUID
    issued_by_username: Optional[str] = None
    scope: DirectiveScope
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    target_user_id: Optional[UUID] = None
    target_username: Optional[str] = None
    priority: DirectivePriority
    effective_date: date
    deadline: Optional[date] = None
    status: DirectiveStatus
    requires_acknowledgement: bool
    created_at: datetime
    updated_at: datetime
    acknowledgements: List[DirectiveAcknowledgementResponse] = []
    total_acknowledgements: int = 0
    acknowledged_count: int = 0


class DirectiveListResponse(BaseModel):
    total: int
    items: List[DirectiveResponse]


# -----------------------------------------------------------------------------
# Notifications Schemas
# -----------------------------------------------------------------------------

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_id: UUID
    notification_type: NotificationType
    title: str
    message: str
    related_resource_type: Optional[str] = None
    related_resource_id: Optional[UUID] = None
    read_status: NotificationReadStatus
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    items: List[NotificationResponse]



# -----------------------------------------------------------------------------
# Communication Log Schemas
# -----------------------------------------------------------------------------

class CommunicationLogCreate(BaseModel):
    date_time: Optional[datetime] = None
    communication_type: CommunicationType = CommunicationType.OFFICIAL_MESSAGE
    subject: str = Field(..., min_length=3, max_length=255)
    sender_info: str = Field(..., min_length=2, max_length=255)
    recipient_info: str = Field(..., min_length=2, max_length=255)
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    related_resource_type: Optional[str] = Field(None, max_length=50)
    related_resource_id: Optional[UUID] = None
    reference_link: Optional[str] = Field(None, max_length=1024)
    remarks: Optional[str] = None


class CommunicationLogUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=3, max_length=255)
    sender_info: Optional[str] = Field(None, min_length=2, max_length=255)
    recipient_info: Optional[str] = Field(None, min_length=2, max_length=255)
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    reference_link: Optional[str] = Field(None, max_length=1024)
    remarks: Optional[str] = None
    status: Optional[CommunicationLogStatus] = None


class CommunicationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date_time: datetime
    communication_type: CommunicationType
    subject: str
    sender_info: str
    recipient_info: str
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    related_resource_type: Optional[str] = None
    related_resource_id: Optional[UUID] = None
    reference_link: Optional[str] = None
    remarks: Optional[str] = None
    created_by_id: UUID
    created_by_username: Optional[str] = None
    status: CommunicationLogStatus
    created_at: datetime
    updated_at: datetime


class CommunicationLogListResponse(BaseModel):
    total: int
    items: List[CommunicationLogResponse]
