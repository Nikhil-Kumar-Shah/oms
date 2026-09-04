"""
Ownership Transfer & Account Succession Governance Service Layer
Enforces atomic ownership handoff, account succession, self-approval prevention,
vertical scope verification, and authoritative resource mutation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.communication import NotificationType
from app.models.event import Event
from app.models.governance import OwnershipTransfer, TransferResourceType, TransferStatus
from app.models.organization import UserVertical
from app.models.requirement import Requirement, RequirementStatus
from app.models.task import Task, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.governance import (
    AccountSuccessionPreviewResponse,
    OwnershipTransferCreate,
    OwnershipTransferReviewRequest,
    SuccessionEventSummary,
    SuccessionTaskSummary,
    SuccessionUserSummary,
    SuccessionVerticalSummary,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class OwnershipTransferService:
    """Manages resource ownership transfer and account succession workflows."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)

    def preview_account_succession(
        self,
        previous_user_id: UUID,
        successor_user_id: UUID,
    ) -> AccountSuccessionPreviewResponse:
        """
        Generates a dry-run preview of an Account Ownership Succession.
        Calculates all active operational responsibilities that will transition to the successor,
        verifying that historical completed work, past reports, and audit logs remain untouched.
        """
        previous_user = self.db.scalar(
            select(User)
            .where(User.id == previous_user_id)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals).selectinload(UserVertical.vertical),
            )
        )
        if not previous_user:
            raise EntityNotFoundException(f"Previous user '{previous_user_id}' not found")

        successor_user = self.db.scalar(
            select(User)
            .where(User.id == successor_user_id)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals).selectinload(UserVertical.vertical),
            )
        )
        if not successor_user:
            raise EntityNotFoundException(f"Successor user '{successor_user_id}' not found")

        if previous_user_id == successor_user_id:
            raise ValidationException("Previous account and Successor account cannot be the same user")

        # 1. Query Active Tasks assigned to Previous User (Completed/Cancelled remain historical)
        active_tasks_stmt = (
            select(Task)
            .options(selectinload(Task.vertical))
            .where(
                Task.assigned_to_id == previous_user_id,
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
        )
        active_tasks = list(self.db.scalars(active_tasks_stmt).all())

        # 2. Query Active Events where Previous User is Primary POC or Event Head
        active_events_stmt = select(Event).where(
            (Event.primary_poc_id == previous_user_id) | (Event.event_head_id == previous_user_id)
        )
        active_events = list(self.db.scalars(active_events_stmt).all())

        # 3. Query Active Requirements assigned to Previous User
        active_reqs_stmt = select(Requirement).where(
            Requirement.assignee_id == previous_user_id,
            Requirement.status.notin_([RequirementStatus.COMPLETED, RequirementStatus.CANCELLED, RequirementStatus.REJECTED]),
        )
        active_reqs = list(self.db.scalars(active_reqs_stmt).all())

        # 4. Vertical Assignments
        assigned_verticals = [
            SuccessionVerticalSummary(
                id=uv.vertical.id,
                name=uv.vertical.name,
                is_primary=uv.is_primary,
            )
            for uv in previous_user.user_verticals
            if uv.vertical
        ]

        prev_role_name = previous_user.user_roles[0].role.name if previous_user.user_roles and previous_user.user_roles[0].role else None
        succ_role_name = successor_user.user_roles[0].role.name if successor_user.user_roles and successor_user.user_roles[0].role else None

        return AccountSuccessionPreviewResponse(
            previous_user=SuccessionUserSummary(
                id=previous_user.id,
                username=previous_user.username,
                full_name=previous_user.full_name,
                email=previous_user.email,
                account_status=previous_user.account_status.value,
                role_name=prev_role_name,
            ),
            successor_user=SuccessionUserSummary(
                id=successor_user.id,
                username=successor_user.username,
                full_name=successor_user.full_name,
                email=successor_user.email,
                account_status=successor_user.account_status.value,
                role_name=succ_role_name,
            ),
            active_tasks_count=len(active_tasks),
            active_tasks=[
                SuccessionTaskSummary(
                    id=t.id,
                    title=t.title,
                    priority=t.priority.value,
                    status=t.status.value,
                    vertical_name=t.vertical.name if t.vertical else None,
                )
                for t in active_tasks
            ],
            active_events_count=len(active_events),
            active_events=[
                SuccessionEventSummary(
                    id=e.id,
                    name=e.name,
                    status=e.status.value,
                    role="Primary POC" if e.primary_poc_id == previous_user_id else "Event Head",
                )
                for e in active_events
            ],
            active_requirements_count=len(active_reqs),
            assigned_verticals=assigned_verticals,
        )

    def request_transfer(self, data: OwnershipTransferCreate, requested_by_id: UUID) -> OwnershipTransfer:
        target_user = self.db.get(User, data.requested_owner_id)
        if not target_user or target_user.account_status != AccountStatus.ACTIVE:
            raise ValidationException("Target successor / requested owner must exist and have ACTIVE account status")

        current_owner_id: Optional[UUID] = None
        resource_vertical_id: Optional[UUID] = None

        if data.resource_type == TransferResourceType.ACCOUNT:
            previous_user = self.db.get(User, data.resource_id)
            if not previous_user:
                raise EntityNotFoundException(f"Previous user account '{data.resource_id}' not found")
            if data.resource_id == data.requested_owner_id:
                raise ValidationException("Previous account and Successor account cannot be the same user")
            current_owner_id = previous_user.id

        elif data.resource_type == TransferResourceType.TASK:
            task = self.db.get(Task, data.resource_id)
            if not task:
                raise EntityNotFoundException(f"Task '{data.resource_id}' not found")
            current_owner_id = task.assigned_to_id or task.assigned_by_id
            resource_vertical_id = task.vertical_id

        elif data.resource_type == TransferResourceType.EVENT:
            event = self.db.get(Event, data.resource_id)
            if not event:
                raise EntityNotFoundException(f"Event '{data.resource_id}' not found")
            current_owner_id = event.primary_poc_id or event.event_head_id or event.created_by_id
            resource_vertical_id = event.vertical_id

        elif data.resource_type == TransferResourceType.REQUIREMENT:
            req = self.db.get(Requirement, data.resource_id)
            if not req:
                raise EntityNotFoundException(f"Requirement '{data.resource_id}' not found")
            current_owner_id = req.assignee_id or req.requester_id
            resource_vertical_id = req.target_vertical_id

        if not current_owner_id:
            current_owner_id = requested_by_id

        # Verify target user is in the resource's vertical scope if scoped (for non-account transfers)
        if resource_vertical_id:
            is_in_vert = self.db.scalar(
                select(UserVertical).where(
                    UserVertical.user_id == data.requested_owner_id,
                    UserVertical.vertical_id == resource_vertical_id,
                )
            )
            if not is_in_vert:
                raise ValidationException("Target requested owner is not assigned to the resource's vertical division")

        transfer = OwnershipTransfer(
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            current_owner_id=current_owner_id,
            requested_owner_id=data.requested_owner_id,
            requested_by_id=requested_by_id,
            reason=data.reason,
            status=TransferStatus.PENDING,
        )
        self.db.add(transfer)
        self.db.flush()

        audit_action = (
            "ACCOUNT_SUCCESSION_REQUEST"
            if data.resource_type == TransferResourceType.ACCOUNT
            else "OWNERSHIP_TRANSFER_REQUEST"
        )

        self.audit.log(
            action=audit_action,
            resource_type="OWNERSHIP_TRANSFER",
            resource_id=str(transfer.id),
            outcome="SUCCESS",
            actor_id=requested_by_id,
            details={
                "resource_type": transfer.resource_type.value,
                "resource_id": str(transfer.resource_id),
                "previous_owner_id": str(transfer.current_owner_id),
                "requested_owner_id": str(transfer.requested_owner_id),
                "reason": transfer.reason,
            },
        )

        # Notify current owner & target owner
        self.notif_service.create_notification(
            recipient_id=transfer.requested_owner_id,
            title=f"Ownership Succession Request: {transfer.resource_type.value}",
            message=f"You have been requested to assume responsibilities from ({transfer.current_owner_id}). Reason: {transfer.reason}",
            notification_type=NotificationType.TRANSFER,
            related_resource_type=transfer.resource_type.value,
            related_resource_id=transfer.resource_id,
        )

        logger.info(f"Created OwnershipTransfer / Account Succession request (id={transfer.id})")
        return transfer

    def get_transfer_by_id(self, transfer_id: UUID) -> OwnershipTransfer:
        transfer = self.db.scalar(
            select(OwnershipTransfer)
            .where(OwnershipTransfer.id == transfer_id)
            .options(
                selectinload(OwnershipTransfer.current_owner),
                selectinload(OwnershipTransfer.requested_owner),
                selectinload(OwnershipTransfer.requested_by),
                selectinload(OwnershipTransfer.reviewed_by),
            )
        )
        if not transfer:
            raise EntityNotFoundException(f"Ownership transfer '{transfer_id}' not found")
        return transfer

    def list_transfers(
        self,
        resource_type: Optional[TransferResourceType] = None,
        status: Optional[TransferStatus] = None,
        user_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[OwnershipTransfer], int]:
        stmt = select(OwnershipTransfer).options(
            selectinload(OwnershipTransfer.current_owner),
            selectinload(OwnershipTransfer.requested_owner),
            selectinload(OwnershipTransfer.requested_by),
            selectinload(OwnershipTransfer.reviewed_by),
        )
        count_stmt = select(func.count(OwnershipTransfer.id))

        if resource_type:
            stmt = stmt.where(OwnershipTransfer.resource_type == resource_type)
            count_stmt = count_stmt.where(OwnershipTransfer.resource_type == resource_type)
        if status:
            stmt = stmt.where(OwnershipTransfer.status == status)
            count_stmt = count_stmt.where(OwnershipTransfer.status == status)
        if user_id:
            clause = (
                (OwnershipTransfer.current_owner_id == user_id)
                | (OwnershipTransfer.requested_owner_id == user_id)
                | (OwnershipTransfer.requested_by_id == user_id)
            )
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        total = self.db.scalar(count_stmt) or 0
        items = list(
            self.db.scalars(
                stmt.order_by(OwnershipTransfer.created_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return items, total

    def review_transfer(
        self,
        transfer_id: UUID,
        reviewer_id: UUID,
        data: OwnershipTransferReviewRequest,
    ) -> OwnershipTransfer:
        transfer = self.get_transfer_by_id(transfer_id)
        if transfer.status != TransferStatus.PENDING:
            raise ValidationException(f"Cannot review transfer with status '{transfer.status.value}'")

        # Self-approval prohibition
        if transfer.requested_by_id == reviewer_id:
            raise ForbiddenException("Self-approval prohibited: Requester cannot approve their own transfer request")

        now = datetime.now(timezone.utc)
        transfer.status = data.status
        transfer.reviewed_at = now
        transfer.reviewed_by_id = reviewer_id
        if data.remarks:
            transfer.remarks = data.remarks

        tasks_reassigned = 0
        events_reassigned = 0
        reqs_reassigned = 0

        if data.status == TransferStatus.APPROVED:
            # -----------------------------------------------------------------
            # A. ACCOUNT SUCCESSION HANDOFF
            # -----------------------------------------------------------------
            if transfer.resource_type == TransferResourceType.ACCOUNT:
                previous_user = self.db.scalar(
                    select(User)
                    .where(User.id == transfer.resource_id)
                    .options(selectinload(User.user_verticals))
                )
                successor_user = self.db.scalar(
                    select(User)
                    .where(User.id == transfer.requested_owner_id)
                    .options(selectinload(User.user_verticals))
                )

                if not previous_user or not successor_user:
                    raise EntityNotFoundException("Previous user or successor user account not found during review")

                # 1. Reassign all ACTIVE tasks to successor (Historical completed/cancelled tasks remain untouched)
                active_tasks = list(
                    self.db.scalars(
                        select(Task).where(
                            Task.assigned_to_id == previous_user.id,
                            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                        )
                    ).all()
                )
                for t in active_tasks:
                    t.assigned_to_id = successor_user.id
                tasks_reassigned = len(active_tasks)

                # 2. Reassign current Event POC & Event Head responsibilities
                events_as_poc = list(
                    self.db.scalars(
                        select(Event).where(Event.primary_poc_id == previous_user.id)
                    ).all()
                )
                for e in events_as_poc:
                    e.primary_poc_id = successor_user.id

                events_as_head = list(
                    self.db.scalars(
                        select(Event).where(Event.event_head_id == previous_user.id)
                    ).all()
                )
                for e in events_as_head:
                    e.event_head_id = successor_user.id
                events_reassigned = len(events_as_poc) + len(events_as_head)

                # 3. Reassign active Requirements
                active_reqs = list(
                    self.db.scalars(
                        select(Requirement).where(
                            Requirement.assignee_id == previous_user.id,
                            Requirement.status.notin_([RequirementStatus.COMPLETED, RequirementStatus.CANCELLED, RequirementStatus.REJECTED]),
                        )
                    ).all()
                )
                for r in active_reqs:
                    r.assignee_id = successor_user.id
                reqs_reassigned = len(active_reqs)

                # 4. Copy vertical assignments to successor if missing
                succ_vert_ids = {uv.vertical_id for uv in successor_user.user_verticals}
                for uv in previous_user.user_verticals:
                    if uv.vertical_id not in succ_vert_ids:
                        self.db.add(
                            UserVertical(
                                user_id=successor_user.id,
                                vertical_id=uv.vertical_id,
                                is_primary=uv.is_primary,
                            )
                        )

                # 5. Transition Previous User account to DISABLED / departed state
                previous_user.account_status = AccountStatus.DISABLED
                previous_user.disabled_at = now

                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = now

            # -----------------------------------------------------------------
            # B. SPECIFIC RESOURCE TRANSFER HANDOFF
            # -----------------------------------------------------------------
            elif transfer.resource_type == TransferResourceType.TASK:
                task = self.db.get(Task, transfer.resource_id)
                if task:
                    task.assigned_to_id = transfer.requested_owner_id
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = now

            elif transfer.resource_type == TransferResourceType.EVENT:
                event = self.db.get(Event, transfer.resource_id)
                if event:
                    event.primary_poc_id = transfer.requested_owner_id
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = now

            elif transfer.resource_type == TransferResourceType.REQUIREMENT:
                req = self.db.get(Requirement, transfer.resource_id)
                if req:
                    req.assignee_id = transfer.requested_owner_id
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = now

        audit_action = (
            "ACCOUNT_SUCCESSION_REVIEW"
            if transfer.resource_type == TransferResourceType.ACCOUNT
            else "OWNERSHIP_TRANSFER_REVIEW"
        )

        self.audit.log(
            action=audit_action,
            resource_type="OWNERSHIP_TRANSFER",
            resource_id=str(transfer.id),
            outcome="SUCCESS",
            actor_id=reviewer_id,
            details={
                "status": transfer.status.value,
                "remarks": transfer.remarks,
                "resource_type": transfer.resource_type.value,
                "tasks_reassigned": tasks_reassigned,
                "events_reassigned": events_reassigned,
                "requirements_reassigned": reqs_reassigned,
            },
        )

        # Notify requester & new owner
        self.notif_service.create_notification(
            recipient_id=transfer.requested_by_id,
            title=f"Ownership Transfer {transfer.status.value}",
            message=f"Succession / transfer request for {transfer.resource_type.value} was {transfer.status.value} by reviewer.",
            notification_type=NotificationType.TRANSFER,
            related_resource_type=transfer.resource_type.value,
            related_resource_id=transfer.resource_id,
        )

        return transfer
