"""
Directive & Acknowledgement Service Layer
Manages operational instructions, governance compliance, and individual acknowledgement rosters.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.communication import (
    AcknowledgementStatus,
    Directive,
    DirectiveAcknowledgement,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
    Notification,
    NotificationType,
)
from app.models.organization import UserVertical, Vertical
from app.models.user import AccountStatus, User
from app.schemas.communication import DirectiveAcknowledgeRequest, DirectiveCreate, DirectiveUpdate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class DirectiveService:
    """Manages operational directives and structured acknowledgement tracking."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)

    def create_directive(self, data: DirectiveCreate, issued_by_id: UUID) -> Directive:
        if data.scope == DirectiveScope.VERTICAL:
            if not data.vertical_id:
                raise ValidationException("Vertical ID is required when scope is VERTICAL")
            vert = self.db.get(Vertical, data.vertical_id)
            if not vert:
                raise ValidationException("Target vertical not found")

        if data.scope == DirectiveScope.USER:
            if not data.target_user_id:
                raise ValidationException("Target user ID is required when scope is USER")
            u = self.db.get(User, data.target_user_id)
            if not u:
                raise ValidationException("Target user not found")

        status = DirectiveStatus.ISSUED if data.issue_now else DirectiveStatus.DRAFT

        directive = Directive(
            title=data.title,
            instruction=data.instruction,
            issued_by_id=issued_by_id,
            scope=data.scope,
            vertical_id=data.vertical_id,
            target_user_id=data.target_user_id,
            priority=data.priority,
            effective_date=data.effective_date,
            deadline=data.deadline,
            status=status,
            requires_acknowledgement=data.requires_acknowledgement,
        )
        self.db.add(directive)
        self.db.flush()

        self.audit.log(
            action="DIRECTIVE_CREATE",
            resource_type="DIRECTIVE",
            resource_id=str(directive.id),
            outcome="SUCCESS",
            actor_id=issued_by_id,
            details={"title": directive.title, "scope": directive.scope.value, "status": directive.status.value},
        )

        if data.issue_now:
            self._on_directive_issued(directive)

        logger.info(f"Created Directive '{directive.title}' (id={directive.id})")
        return directive

    def get_directive_by_id(self, directive_id: UUID) -> Directive:
        directive = self.db.scalar(
            select(Directive)
            .where(Directive.id == directive_id)
            .options(
                selectinload(Directive.issued_by),
                selectinload(Directive.vertical),
                selectinload(Directive.target_user),
                selectinload(Directive.acknowledgements).selectinload(DirectiveAcknowledgement.user),
            )
        )
        if not directive:
            raise EntityNotFoundException(f"Directive '{directive_id}' not found")
        return directive

    def list_directives(
        self,
        current_user: User,
        user_vertical_ids: List[UUID],
        status: Optional[DirectiveStatus] = None,
        is_admin: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Directive], int]:
        stmt = select(Directive).options(
            selectinload(Directive.issued_by),
            selectinload(Directive.vertical),
            selectinload(Directive.target_user),
            selectinload(Directive.acknowledgements).selectinload(DirectiveAcknowledgement.user),
        )
        count_stmt = select(func.count(Directive.id))

        if not is_admin:
            vis_clause = or_(
                Directive.scope == DirectiveScope.ALL,
                Directive.issued_by_id == current_user.id,
                Directive.target_user_id == current_user.id,
                (Directive.scope == DirectiveScope.VERTICAL) & (Directive.vertical_id.in_(user_vertical_ids)),
            )
            stmt = stmt.where(vis_clause)
            count_stmt = count_stmt.where(vis_clause)

        if status:
            stmt = stmt.where(Directive.status == status)
            count_stmt = count_stmt.where(Directive.status == status)

        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(stmt.order_by(Directive.created_at.desc()).offset(offset).limit(limit)).all())
        return items, total

    def update_directive(self, directive_id: UUID, data: DirectiveUpdate, actor_id: UUID) -> Directive:
        directive = self.get_directive_by_id(directive_id)
        if directive.status in [DirectiveStatus.COMPLETED, DirectiveStatus.CANCELLED, DirectiveStatus.ARCHIVED]:
            raise ValidationException(f"Cannot update directive in {directive.status.value} status")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(directive, key, value)

        self.audit.log(
            action="DIRECTIVE_UPDATE",
            resource_type="DIRECTIVE",
            resource_id=str(directive.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return directive

    def issue_directive(self, directive_id: UUID, actor_id: UUID) -> Directive:
        directive = self.get_directive_by_id(directive_id)
        directive.status = DirectiveStatus.ISSUED

        self.audit.log(
            action="DIRECTIVE_ISSUE",
            resource_type="DIRECTIVE",
            resource_id=str(directive.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": directive.title},
        )
        self._on_directive_issued(directive)
        return directive

    def acknowledge_directive(
        self,
        directive_id: UUID,
        user_id: UUID,
        data: DirectiveAcknowledgeRequest,
    ) -> DirectiveAcknowledgement:
        directive = self.get_directive_by_id(directive_id)
        if not directive.requires_acknowledgement:
            raise ValidationException("This directive does not require acknowledgement")

        if directive.status not in [DirectiveStatus.ISSUED, DirectiveStatus.IN_PROGRESS]:
            raise ValidationException(f"Directives cannot be acknowledged in {directive.status.value} state")

        ack = self.db.scalar(
            select(DirectiveAcknowledgement).where(
                DirectiveAcknowledgement.directive_id == directive.id,
                DirectiveAcknowledgement.user_id == user_id,
            )
        )
        if ack and ack.status == AcknowledgementStatus.ACKNOWLEDGED:
            raise ValidationException("Directive has already been acknowledged by this user")

        if not ack:
            # If not in initialized roster, create explicit acknowledgement
            ack = DirectiveAcknowledgement(
                directive_id=directive.id,
                user_id=user_id,
            )
            self.db.add(ack)

        ack.status = AcknowledgementStatus.ACKNOWLEDGED
        ack.acknowledged_at = datetime.now(timezone.utc)
        if data.notes:
            ack.notes = data.notes

        self.db.flush()
        self.audit.log(
            action="DIRECTIVE_ACKNOWLEDGE",
            resource_type="DIRECTIVE_ACKNOWLEDGEMENT",
            resource_id=str(ack.id),
            outcome="SUCCESS",
            actor_id=user_id,
            details={"directive_id": str(directive.id)},
        )
        return ack

    def _on_directive_issued(self, directive: Directive):
        """Initializes acknowledgement roster and dispatches notifications."""
        recipients: List[UUID] = []
        if directive.scope == DirectiveScope.USER and directive.target_user_id:
            recipients = [directive.target_user_id]
        elif directive.scope == DirectiveScope.VERTICAL and directive.vertical_id:
            user_ids = self.db.scalars(
                select(UserVertical.user_id).where(UserVertical.vertical_id == directive.vertical_id)
            ).all()
            recipients = list(set(user_ids))
        elif directive.scope == DirectiveScope.ALL:
            active_users = self.db.scalars(
                select(User.id).where(User.account_status == AccountStatus.ACTIVE)
            ).all()
            recipients = list(active_users)

        if directive.requires_acknowledgement and recipients:
            existing_user_ids = set(
                self.db.scalars(
                    select(DirectiveAcknowledgement.user_id).where(
                        DirectiveAcknowledgement.directive_id == directive.id,
                        DirectiveAcknowledgement.user_id.in_(recipients),
                    )
                ).all()
            )
            new_acks = [
                DirectiveAcknowledgement(
                    directive_id=directive.id,
                    user_id=uid,
                    status=AcknowledgementStatus.PENDING,
                )
                for uid in recipients
                if uid not in existing_user_ids
            ]
            if new_acks:
                self.db.add_all(new_acks)

        self.notif_service.create_batch_notifications(
            recipient_ids=recipients,
            title=f"Operational Directive: {directive.title}",
            message=f"[Priority: {directive.priority.value}] {directive.instruction[:150]}...",
            notification_type=NotificationType.DIRECTIVE,
            related_resource_type="DIRECTIVE",
            related_resource_id=directive.id,
            exclude_user_id=directive.issued_by_id,
        )

