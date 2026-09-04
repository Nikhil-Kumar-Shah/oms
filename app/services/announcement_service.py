"""
Announcement Service Layer
Manages broadcast informational announcements, targeting, publishing, and scoping.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.communication import (
    Announcement,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    Notification,
    NotificationType,
)
from app.models.event import Event, EventMember, EventTeamProfile
from app.models.organization import UserVertical, Vertical
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.schemas.communication import AnnouncementCreate, AnnouncementUpdate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class AnnouncementService:
    """Manages organizational announcements and scope-based visibility."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)

    def create_announcement(self, data: AnnouncementCreate, author_id: UUID) -> Announcement:
        if data.scope == AnnouncementScope.VERTICAL:
            if not data.vertical_id:
                raise ValidationException("Vertical ID is required when scope is VERTICAL")
            vert = self.db.get(Vertical, data.vertical_id)
            if not vert:
                raise ValidationException("Target vertical not found")

        if data.scope in [AnnouncementScope.EVENT, AnnouncementScope.EVENT_TEAM]:
            if not data.event_id:
                raise ValidationException(f"Event ID is required when scope is {data.scope.value}")
            event = self.db.get(Event, data.event_id)
            if not event:
                raise ValidationException("Target event not found")

        if data.scope == AnnouncementScope.USER:
            if not data.target_user_id:
                raise ValidationException("Target User ID is required when scope is USER")
            u = self.db.get(User, data.target_user_id)
            if not u:
                raise ValidationException("Target user not found")

        now = datetime.now(timezone.utc)
        status = AnnouncementStatus.PUBLISHED if data.publish_now else AnnouncementStatus.DRAFT
        pub_time = now if data.publish_now else None

        stored_scope = AnnouncementScope.ALL if data.scope == AnnouncementScope.ORGANIZATION else data.scope

        announcement = Announcement(
            title=data.title,
            content=data.content,
            category=data.category,
            priority=data.priority,
            scope=stored_scope,
            vertical_id=data.vertical_id,
            event_id=data.event_id,
            target_user_id=data.target_user_id,
            author_id=author_id,
            status=status,
            published_at=pub_time,
            expires_at=data.expires_at,
        )
        self.db.add(announcement)
        self.db.flush()

        self.audit.log(
            action="ANNOUNCEMENT_CREATE",
            resource_type="ANNOUNCEMENT",
            resource_id=str(announcement.id),
            outcome="SUCCESS",
            actor_id=author_id,
            details={"title": announcement.title, "scope": announcement.scope.value, "status": announcement.status.value},
        )

        if data.publish_now:
            self._dispatch_announcement_notifications(announcement)

        logger.info(f"Created Announcement '{announcement.title}' (id={announcement.id})")
        return announcement

    def get_announcement_by_id(self, announcement_id: UUID) -> Announcement:
        announcement = self.db.scalar(
            select(Announcement)
            .where(Announcement.id == announcement_id)
            .options(
                selectinload(Announcement.author),
                selectinload(Announcement.vertical),
                selectinload(Announcement.event),
                selectinload(Announcement.target_user),
            )
        )
        if not announcement:
            raise EntityNotFoundException(f"Announcement '{announcement_id}' not found")
        return announcement

    def list_announcements(
        self,
        current_user: User,
        user_vertical_ids: List[UUID],
        status: Optional[AnnouncementStatus] = None,
        is_admin: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Announcement], int]:
        stmt = select(Announcement).options(
            selectinload(Announcement.author),
            selectinload(Announcement.vertical),
            selectinload(Announcement.event),
            selectinload(Announcement.target_user),
        )
        count_stmt = select(func.count(Announcement.id))

        if not is_admin:
            # Check if current user is an EVENT_TEAM account
            roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
            if not roles:
                roles = [
                    r.name
                    for r in self.db.scalars(
                        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == current_user.id)
                    ).all()
                ]

            if "EVENT_TEAM" in roles and "ADMIN" not in roles and "SPORTS_CORE" not in roles:
                profile = self.db.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == current_user.id))
                team_event_id = profile.event_id if profile else None
                vis_clause = or_(
                    Announcement.scope.in_([AnnouncementScope.ALL, AnnouncementScope.ORGANIZATION]),
                    Announcement.scope == AnnouncementScope.EVENT_TEAM,
                    (Announcement.scope == AnnouncementScope.EVENT) & (Announcement.event_id == team_event_id),
                )
            else:
                # Internal staff visibility check
                vis_clause = or_(
                    Announcement.scope.in_([AnnouncementScope.ALL, AnnouncementScope.ORGANIZATION]),
                    Announcement.author_id == current_user.id,
                    Announcement.target_user_id == current_user.id,
                    (Announcement.scope == AnnouncementScope.VERTICAL) & (Announcement.vertical_id.in_(user_vertical_ids)),
                    Announcement.scope.in_([AnnouncementScope.EVENT, AnnouncementScope.EVENT_TEAM]),
                )

            stmt = stmt.where(vis_clause)
            count_stmt = count_stmt.where(vis_clause)

        if status:
            stmt = stmt.where(Announcement.status == status)
            count_stmt = count_stmt.where(Announcement.status == status)

        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(stmt.order_by(Announcement.created_at.desc()).offset(offset).limit(limit)).all())
        return items, total

    def update_announcement(self, announcement_id: UUID, data: AnnouncementUpdate, actor_id: UUID) -> Announcement:
        announcement = self.get_announcement_by_id(announcement_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(announcement, key, value)

        self.audit.log(
            action="ANNOUNCEMENT_UPDATE",
            resource_type="ANNOUNCEMENT",
            resource_id=str(announcement.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return announcement

    def publish_announcement(self, announcement_id: UUID, actor_id: UUID) -> Announcement:
        announcement = self.get_announcement_by_id(announcement_id)
        announcement.status = AnnouncementStatus.PUBLISHED
        announcement.published_at = datetime.now(timezone.utc)

        self.audit.log(
            action="ANNOUNCEMENT_PUBLISH",
            resource_type="ANNOUNCEMENT",
            resource_id=str(announcement.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": announcement.title},
        )
        self._dispatch_announcement_notifications(announcement)
        return announcement

    def archive_announcement(self, announcement_id: UUID, actor_id: UUID) -> Announcement:
        announcement = self.get_announcement_by_id(announcement_id)
        announcement.status = AnnouncementStatus.ARCHIVED
        announcement.archived_at = datetime.now(timezone.utc)

        self.audit.log(
            action="ANNOUNCEMENT_ARCHIVE",
            resource_type="ANNOUNCEMENT",
            resource_id=str(announcement.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": announcement.title},
        )
        return announcement

    def _dispatch_announcement_notifications(self, announcement: Announcement):
        """Dispatches attention notifications to users within announcement scope."""
        recipients: List[UUID] = []
        if announcement.scope == AnnouncementScope.USER and announcement.target_user_id:
            recipients = [announcement.target_user_id]
        elif announcement.scope == AnnouncementScope.VERTICAL and announcement.vertical_id:
            user_ids = self.db.scalars(
                select(UserVertical.user_id).where(UserVertical.vertical_id == announcement.vertical_id)
            ).all()
            recipients = list(set(user_ids))
        elif announcement.scope in [AnnouncementScope.EVENT, AnnouncementScope.EVENT_TEAM] and announcement.event_id:
            team_user_ids = self.db.scalars(
                select(EventTeamProfile.user_id).where(EventTeamProfile.event_id == announcement.event_id)
            ).all()
            member_user_ids = self.db.scalars(
                select(EventMember.user_id).where(EventMember.event_id == announcement.event_id)
            ).all()
            recipients = list(set(list(team_user_ids) + list(member_user_ids)))
        elif announcement.scope in [AnnouncementScope.ALL, AnnouncementScope.ORGANIZATION]:
            active_users = self.db.scalars(
                select(User.id).where(User.account_status == AccountStatus.ACTIVE)
            ).all()
            recipients = list(active_users)

        self.notif_service.create_batch_notifications(
            recipient_ids=recipients,
            title=f"Announcement: {announcement.title}",
            message=f"[{announcement.category}] {announcement.content[:150]}...",
            notification_type=NotificationType.ANNOUNCEMENT,
            related_resource_type="ANNOUNCEMENT",
            related_resource_id=announcement.id,
            exclude_user_id=announcement.author_id,
        )

