"""
Notification Service Layer
Internal attention mechanism alerting users to operational changes.
Guarantees user isolation and strictly server-authoritative creation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.exceptions import EntityNotFoundException, ForbiddenException
from app.core.logging import get_logger
from app.models.communication import (
    Notification,
    NotificationReadStatus,
    NotificationType,
)
from app.models.user import AccountStatus, User

logger = get_logger(__name__)


class NotificationService:
    """Manages server-generated user notifications."""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        recipient_id: UUID,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM,
        related_resource_type: Optional[str] = None,
        related_resource_id: Optional[UUID] = None,
    ) -> Optional[Notification]:
        """Server-internal dispatcher to generate user notification."""
        user = self.db.get(User, recipient_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            return None

        notif = Notification(
            recipient_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_resource_type=related_resource_type,
            related_resource_id=related_resource_id,
            read_status=NotificationReadStatus.UNREAD,
        )
        self.db.add(notif)
        self.db.flush()
        return notif

    def create_batch_notifications(
        self,
        recipient_ids: List[UUID],
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM,
        related_resource_type: Optional[str] = None,
        related_resource_id: Optional[UUID] = None,
        exclude_user_id: Optional[UUID] = None,
    ) -> List[Notification]:
        """Bulk dispatcher for multi-user notifications (e.g. announcements, directives, forms)."""
        if not recipient_ids:
            return []

        unique_recipients = set(recipient_ids)
        if exclude_user_id:
            unique_recipients.discard(exclude_user_id)

        if not unique_recipients:
            return []

        active_user_ids = set(
            self.db.scalars(
                select(User.id).where(
                    User.id.in_(list(unique_recipients)),
                    User.account_status == AccountStatus.ACTIVE,
                )
            ).all()
        )

        notifications = [
            Notification(
                recipient_id=uid,
                notification_type=notification_type,
                title=title,
                message=message,
                related_resource_type=related_resource_type,
                related_resource_id=related_resource_id,
                read_status=NotificationReadStatus.UNREAD,
            )
            for uid in active_user_ids
        ]
        if notifications:
            self.db.add_all(notifications)
            self.db.flush()
        return notifications

    def get_unread_count(self, user_id: UUID) -> int:
        """Lightweight and ultra-fast index-driven unread count query."""
        stmt = select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.read_status == NotificationReadStatus.UNREAD,
        )
        return self.db.scalar(stmt) or 0

    def list_user_notifications(
        self,
        user_id: UUID,
        read_status: Optional[NotificationReadStatus] = None,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Notification], int, int]:
        """Fetch user-scoped notification list with total and unread count."""
        stmt = select(Notification).where(Notification.recipient_id == user_id)
        count_stmt = select(func.count(Notification.id)).where(Notification.recipient_id == user_id)
        unread_stmt = select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.read_status == NotificationReadStatus.UNREAD,
        )

        if read_status:
            stmt = stmt.where(Notification.read_status == read_status)
            count_stmt = count_stmt.where(Notification.read_status == read_status)
        else:
            stmt = stmt.where(Notification.read_status != NotificationReadStatus.DISMISSED)
            count_stmt = count_stmt.where(Notification.read_status != NotificationReadStatus.DISMISSED)


        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
            count_stmt = count_stmt.where(Notification.notification_type == notification_type)

        total = self.db.scalar(count_stmt) or 0
        unread = self.db.scalar(unread_stmt) or 0
        notifs = list(self.db.scalars(stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)).all())
        return notifs, total, unread

    def mark_as_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        """Mark single notification as read with strict user ownership validation."""
        notif = self.db.get(Notification, notification_id)
        if not notif:
            raise EntityNotFoundException(f"Notification '{notification_id}' not found")

        if notif.recipient_id != user_id:
            raise ForbiddenException("You cannot access notifications belonging to another user")

        if notif.read_status == NotificationReadStatus.UNREAD:
            notif.read_status = NotificationReadStatus.READ
            notif.read_at = datetime.now(timezone.utc)
            self.db.flush()

        return notif

    def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all unread notifications belonging strictly to the current user as read."""
        notifs = list(
            self.db.scalars(
                select(Notification).where(
                    Notification.recipient_id == user_id,
                    Notification.read_status == NotificationReadStatus.UNREAD,
                )
            ).all()
        )
        now = datetime.now(timezone.utc)
        for n in notifs:
            n.read_status = NotificationReadStatus.READ
            n.read_at = now

        self.db.flush()
        return len(notifs)

    def dismiss_notification(self, notification_id: UUID, user_id: UUID) -> Notification:
        """Dismiss a notification record belonging to the current user."""
        notif = self.db.get(Notification, notification_id)
        if not notif:
            raise EntityNotFoundException(f"Notification '{notification_id}' not found")

        if notif.recipient_id != user_id:
            raise ForbiddenException("You cannot access notifications belonging to another user")

        notif.read_status = NotificationReadStatus.DISMISSED
        self.db.flush()
        return notif
