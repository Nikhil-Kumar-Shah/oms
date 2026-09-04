"""
Notifications API Endpoints
User-isolated attention mechanisms.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_user_session
from app.core.database import get_db
from app.models.communication import NotificationReadStatus, NotificationType
from app.models.user import User
from app.schemas.communication import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _format_notification_response(n) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        recipient_id=n.recipient_id,
        notification_type=n.notification_type,
        title=n.title,
        message=n.message,
        related_resource_type=n.related_resource_type,
        related_resource_id=n.related_resource_id,
        read_status=n.read_status,
        is_read=n.is_read,
        created_at=n.created_at,
        read_at=n.read_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_my_notifications(
    read_status: Optional[NotificationReadStatus] = Query(None),
    notification_type: Optional[NotificationType] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """List notifications for the current authenticated user with pagination and status filters."""
    service = NotificationService(db)
    items, total, unread = service.list_user_notifications(
        user_id=current_user.id,
        read_status=read_status,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        total=total,
        unread_count=unread,
        items=[_format_notification_response(n) for n in items],
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_my_unread_count(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Ultra-lightweight endpoint returning total unread notifications for the active user."""
    service = NotificationService(db)
    count = service.get_unread_count(user_id=current_user.id)
    return NotificationUnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read. Fails with 403 if belonging to another user."""
    service = NotificationService(db)
    notif = service.mark_as_read(notification_id, user_id=current_user.id)
    db.commit()
    return _format_notification_response(notif)


@router.post("/read-all", response_model=dict)
@router.patch("/read-all", response_model=dict)
def mark_all_notifications_read(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications belonging to the current user as read."""
    service = NotificationService(db)
    count = service.mark_all_as_read(user_id=current_user.id)
    db.commit()
    return {"marked_read_count": count}


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
@router.patch("/{notification_id}/dismiss", response_model=NotificationResponse)
def dismiss_notification(
    notification_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Dismiss a notification record."""
    service = NotificationService(db)
    notif = service.dismiss_notification(notification_id, user_id=current_user.id)
    db.commit()
    return _format_notification_response(notif)
