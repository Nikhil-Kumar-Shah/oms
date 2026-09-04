from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.communication import NotificationType
from app.models.event import Event, EventMember, EventTeamProfile
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.requirement import (
    Requirement,
    RequirementMessage,
    RequirementPriority,
    RequirementStatus,
)
from app.models.user import AccountStatus, User
from app.schemas.requirement import (
    RequirementAssignRequest,
    RequirementCreate,
    RequirementEscalateRequest,
    RequirementForwardRequest,
    RequirementMessageCreate,
    RequirementResolveEscalationRequest,
    RequirementTransitionRequest,
    RequirementUpdate,
)
from app.services.audit_service import AuditService
from app.services.authority_service import AuthorityService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class RequirementService:
    """Manages cross-vertical requirements, escalations, forwarding, messages, and workflow notifications."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)
        self.authority = AuthorityService(db)

    def _validate_user_in_vertical(self, user_id: UUID, vertical_id: UUID, field_name: str = "Assignee"):
        user = self.db.get(User, user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            raise ValidationException(f"{field_name} must exist and have ACTIVE account status")

        assignment = self.db.scalar(
            select(UserVertical).where(
                UserVertical.user_id == user_id,
                UserVertical.vertical_id == vertical_id,
            )
        )
        if not assignment:
            raise ValidationException(f"Cannot assign {field_name.lower()}: User '{user.username}' is not assigned to the target vertical division")
        return user

    def create_requirement(self, data: RequirementCreate, requester_id: UUID) -> Requirement:
        requester = self.db.get(User, requester_id)
        if not requester:
            raise EntityNotFoundException("Requester not found")

        is_event_team = self.authority.is_event_team(requester_id)
        event_id = data.event_id
        responsible_poc_id: Optional[UUID] = None
        assignee_id = data.assignee_id
        requesting_vertical_id = data.requesting_vertical_id
        target_vertical_id = data.target_vertical_id

        # Workflow 1 & 2: Event Team auto-detection & routing
        if is_event_team:
            profile = self.db.scalar(
                select(EventTeamProfile).where(EventTeamProfile.user_id == requester_id)
            )
            if not profile or not profile.event_id:
                raise ValidationException("Event Team user must have an operational profile linked to an event to raise requirements")

            event = self.db.get(Event, profile.event_id)
            if not event:
                raise ValidationException("Linked event does not exist")

            event_id = event.id
            requesting_vertical_id = event.vertical_id
            target_vertical_id = event.vertical_id

            # Route to designated Head POC / Primary POC
            head_poc_id = None
            if profile.contact_info and isinstance(profile.contact_info, dict):
                raw_poc = profile.contact_info.get("head_poc_id")
                if raw_poc:
                    try:
                        head_poc_id = UUID(str(raw_poc))
                    except Exception:
                        pass

            if not head_poc_id:
                head_poc_id = event.primary_poc_id or event.event_head_id

            responsible_poc_id = head_poc_id
            assignee_id = head_poc_id
            initial_status = RequirementStatus.RAISED
        else:
            # Fallback/General creation by internal staff
            if event_id:
                event = self.db.get(Event, event_id)
                if event:
                    if not requesting_vertical_id:
                        requesting_vertical_id = event.vertical_id
                    if not target_vertical_id:
                        target_vertical_id = event.vertical_id
                    responsible_poc_id = event.primary_poc_id or event.event_head_id

            if not requesting_vertical_id or not target_vertical_id:
                # If staff didn't specify target/requesting vertical, attempt fallback to user's assigned verticals
                user_vids = self.authority.get_user_vertical_ids(requester_id)
                if user_vids:
                    requesting_vertical_id = requesting_vertical_id or user_vids[0]
                    target_vertical_id = target_vertical_id or user_vids[0]

            if data.assignee_id and target_vertical_id:
                self._validate_user_in_vertical(data.assignee_id, target_vertical_id, "Assignee")

            initial_status = RequirementStatus.ASSIGNED if assignee_id else RequirementStatus.OPEN

        requirement = Requirement(
            title=data.title,
            description=data.description,
            event_id=event_id,
            responsible_poc_id=responsible_poc_id,
            forward_history=[],
            requesting_vertical_id=requesting_vertical_id,
            target_vertical_id=target_vertical_id,
            requester_id=requester_id,
            assignee_id=assignee_id,
            priority=data.priority,
            status=initial_status,
            deadline=data.deadline,
            remarks=data.remarks,
            reference_link=data.reference_link,
        )
        self.db.add(requirement)
        self.db.flush()

        # Notification trigger for responsible POC / assignee
        target_notify_id = responsible_poc_id or assignee_id
        if target_notify_id and target_notify_id != requester_id:
            event_name_str = f" for event"
            if requirement.event:
                event_name_str = f" for event '{requirement.event.name}'"
            self.notif_service.create_notification(
                recipient_id=target_notify_id,
                notification_type=NotificationType.REQUIREMENT,
                title=f"New Requirement Received: {requirement.title}",
                message=f"A new requirement '{requirement.title}'{event_name_str} has been routed to you.",
                related_resource_type="REQUIREMENT",
                related_resource_id=requirement.id,
            )

        self.audit.log(
            action="REQUIREMENT_CREATE",
            resource_type="REQUIREMENT",
            resource_id=str(requirement.id),
            outcome="SUCCESS",
            actor_id=requester_id,
            details={
                "title": requirement.title,
                "event_id": str(requirement.event_id) if requirement.event_id else None,
                "responsible_poc_id": str(requirement.responsible_poc_id) if requirement.responsible_poc_id else None,
                "assignee_id": str(requirement.assignee_id) if requirement.assignee_id else None,
            },
        )
        logger.info(f"Created Requirement '{requirement.title}' (id={requirement.id})")
        return requirement

    def get_requirement_by_id(self, req_id: UUID, current_user: Optional[User] = None) -> Requirement:
        req = self.db.scalar(
            select(Requirement)
            .where(Requirement.id == req_id)
            .options(
                selectinload(Requirement.event),
                selectinload(Requirement.responsible_poc),
                selectinload(Requirement.requesting_vertical),
                selectinload(Requirement.target_vertical),
                selectinload(Requirement.requester),
                selectinload(Requirement.assignee),
                selectinload(Requirement.escalated_to),
                selectinload(Requirement.escalated_by),
                selectinload(Requirement.escalation_resolved_by),
                selectinload(Requirement.messages).selectinload(RequirementMessage.author),
            )
        )
        if not req:
            raise EntityNotFoundException(f"Requirement with ID '{req_id}' not found")

        if current_user:
            if not self.authority.can_view_requirement(current_user, req):
                raise ForbiddenException("You do not have authorization to view this requirement")

        return req

    def list_requirements(
        self,
        requesting_vertical_id: Optional[UUID] = None,
        target_vertical_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        status: Optional[RequirementStatus] = None,
        priority: Optional[RequirementPriority] = None,
        current_user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Requirement], int]:
        stmt = select(Requirement).options(
            selectinload(Requirement.event),
            selectinload(Requirement.responsible_poc),
            selectinload(Requirement.requesting_vertical),
            selectinload(Requirement.target_vertical),
            selectinload(Requirement.requester),
            selectinload(Requirement.assignee),
            selectinload(Requirement.escalated_to),
            selectinload(Requirement.escalated_by),
        )
        count_stmt = select(func.count(Requirement.id))

        if current_user:
            # Master Requirements Visibility Scoping
            # 1. Sports Core / Deputy Core / Admin see ALL
            if not self.authority.is_executive_or_admin(current_user.id):
                user_id = current_user.id
                conditions = [
                    Requirement.requester_id == user_id,
                    Requirement.assignee_id == user_id,
                    Requirement.responsible_poc_id == user_id,
                    Requirement.escalated_to_id == user_id,
                ]

                # If user is associated with events (as member, POC, or team profile)
                user_events = self.authority.get_user_event_ids(user_id)
                if user_events:
                    conditions.append(Requirement.event_id.in_(user_events))

                # Vertical membership
                user_vids = self.authority.get_user_vertical_ids(user_id)
                if user_vids:
                    conditions.append(Requirement.requesting_vertical_id.in_(user_vids))
                    conditions.append(Requirement.target_vertical_id.in_(user_vids))

                scope_filter = or_(*conditions)
                stmt = stmt.where(scope_filter)
                count_stmt = count_stmt.where(scope_filter)

        if event_id:
            stmt = stmt.where(Requirement.event_id == event_id)
            count_stmt = count_stmt.where(Requirement.event_id == event_id)
        if requesting_vertical_id:
            stmt = stmt.where(Requirement.requesting_vertical_id == requesting_vertical_id)
            count_stmt = count_stmt.where(Requirement.requesting_vertical_id == requesting_vertical_id)
        if target_vertical_id:
            stmt = stmt.where(Requirement.target_vertical_id == target_vertical_id)
            count_stmt = count_stmt.where(Requirement.target_vertical_id == target_vertical_id)
        if status:
            stmt = stmt.where(Requirement.status == status)
            count_stmt = count_stmt.where(Requirement.status == status)
        if priority:
            stmt = stmt.where(Requirement.priority == priority)
            count_stmt = count_stmt.where(Requirement.priority == priority)

        total = self.db.scalar(count_stmt) or 0
        reqs = list(self.db.scalars(stmt.order_by(Requirement.created_at.desc()).offset(offset).limit(limit)).all())
        return reqs, total

    def update_requirement(self, req_id: UUID, data: RequirementUpdate, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(req, key, value)

        self.audit.log(
            action="REQUIREMENT_UPDATE",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return req

    def assign_requirement(self, req_id: UUID, data: RequirementAssignRequest, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        if data.assignee_id:
            if req.target_vertical_id:
                self._validate_user_in_vertical(data.assignee_id, req.target_vertical_id, "Assignee")
            else:
                target_user = self.db.get(User, data.assignee_id)
                if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                    raise ValidationException("Assignee user must exist and have ACTIVE account status")

            req.assignee_id = data.assignee_id
            if req.status in [RequirementStatus.OPEN, RequirementStatus.RAISED]:
                req.status = RequirementStatus.ASSIGNED

            # Notification trigger
            if req.assignee_id != actor_id:
                self.notif_service.create_notification(
                    recipient_id=req.assignee_id,
                    notification_type=NotificationType.REQUIREMENT,
                    title=f"Requirement Assigned: {req.title}",
                    message=f"You have been assigned to requirement '{req.title}'.",
                    related_resource_type="REQUIREMENT",
                    related_resource_id=req.id,
                )
        else:
            req.assignee_id = None
            if req.status == RequirementStatus.ASSIGNED:
                req.status = RequirementStatus.RAISED

        self.audit.log(
            action="REQUIREMENT_ASSIGN",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"assignee_id": str(req.assignee_id) if req.assignee_id else None},
        )
        return req

    def forward_requirement(self, req_id: UUID, data: RequirementForwardRequest, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        actor = self.db.get(User, actor_id)

        if not data.target_user_id and not data.target_vertical_id:
            raise ValidationException("Either target_user_id or target_vertical_id must be provided for forwarding")

        forward_entry: Dict[str, Any] = {
            "forwarded_by_id": str(actor_id),
            "forwarded_by_name": actor.full_name or actor.username if actor else "Staff",
            "reason": data.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Forward to individual user/POC
        if data.target_user_id:
            target_user = self.db.get(User, data.target_user_id)
            if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                raise ValidationException("Target forwarded user must exist and be ACTIVE")

            req.assignee_id = target_user.id
            forward_entry["forwarded_to_id"] = str(target_user.id)
            forward_entry["forwarded_to_name"] = target_user.full_name or target_user.username
            forward_entry["forwarded_to_type"] = "USER"

            # Notify forwarded user
            if target_user.id != actor_id:
                self.notif_service.create_notification(
                    recipient_id=target_user.id,
                    notification_type=NotificationType.REQUIREMENT,
                    title=f"Requirement Forwarded: {req.title}",
                    message=f"Requirement '{req.title}' has been forwarded to you. Reason: {data.reason}",
                    related_resource_type="REQUIREMENT",
                    related_resource_id=req.id,
                )

        # 2. Forward to target vertical
        if data.target_vertical_id:
            target_vert = self.db.get(Vertical, data.target_vertical_id)
            if not target_vert or target_vert.status != VerticalStatus.ACTIVE:
                raise ValidationException("Target vertical division must exist and be ACTIVE")
            req.target_vertical_id = target_vert.id
            if "forwarded_to_id" not in forward_entry:
                forward_entry["forwarded_to_id"] = str(target_vert.id)
                forward_entry["forwarded_to_name"] = target_vert.name
                forward_entry["forwarded_to_type"] = "VERTICAL"

        # Update status to FORWARDED
        req.status = RequirementStatus.FORWARDED

        # Append to history
        hist = list(req.forward_history or [])
        hist.append(forward_entry)
        req.forward_history = hist

        # Append system message to thread so conversation preserves activity
        sys_msg_text = f"Requirement forwarded to {forward_entry['forwarded_to_name']} by {forward_entry['forwarded_by_name']}. Reason: {data.reason}"
        sys_msg = RequirementMessage(
            requirement_id=req.id,
            author_id=actor_id,
            content=f"[SYSTEM ACTIVITY: FORWARDED] {sys_msg_text}",
        )
        self.db.add(sys_msg)
        self.db.flush()

        self.audit.log(
            action="REQUIREMENT_FORWARD",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=forward_entry,
        )
        logger.info(f"Requirement '{req.title}' forwarded to {forward_entry['forwarded_to_name']}")
        return req

    def escalate_requirement(self, req_id: UUID, data: RequirementEscalateRequest, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        actor = self.db.get(User, actor_id)

        if req.status in [RequirementStatus.COMPLETED, RequirementStatus.CANCELLED, RequirementStatus.REJECTED, RequirementStatus.CLOSED]:
            raise ValidationException(f"Cannot escalate requirement in terminal status '{req.status.value}'")

        target_user = self.db.get(User, data.escalated_to_id)
        if not target_user or target_user.account_status != AccountStatus.ACTIVE:
            raise ValidationException("Escalation target user must exist and be active")

        req.is_escalated = True
        req.status = RequirementStatus.ESCALATED
        req.escalated_to_id = data.escalated_to_id
        req.escalated_by_id = actor_id
        req.escalated_at = datetime.now(timezone.utc)
        req.escalation_reason = data.reason
        req.escalation_status = "PENDING_REVIEW"

        # Append system message to thread
        actor_name = actor.full_name or actor.username if actor else "Staff"
        target_name = target_user.full_name or target_user.username
        sys_msg = RequirementMessage(
            requirement_id=req.id,
            author_id=actor_id,
            content=f"[SYSTEM ACTIVITY: ESCALATED] Escalated to {target_name} by {actor_name}. Reason: {data.reason}",
        )
        self.db.add(sys_msg)
        self.db.flush()

        # Notification trigger
        if data.escalated_to_id != actor_id:
            self.notif_service.create_notification(
                recipient_id=data.escalated_to_id,
                notification_type=NotificationType.REQUIREMENT,
                title=f"Requirement Escalation: {req.title}",
                message=f"Requirement '{req.title}' has been escalated to you by {actor_name}. Reason: {data.reason}",
                related_resource_type="REQUIREMENT",
                related_resource_id=req.id,
            )

        self.audit.log(
            action="REQUIREMENT_ESCALATE",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "escalated_to_id": str(data.escalated_to_id),
                "reason": data.reason,
            },
        )
        logger.info(f"Escalated Requirement '{req.title}' (id={req.id}) to {target_user.username}")
        return req

    def resolve_requirement_escalation(self, req_id: UUID, data: RequirementResolveEscalationRequest, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        actor = self.db.get(User, actor_id)
        if not req.is_escalated:
            raise ValidationException("Requirement is not currently in an escalated state")

        req.is_escalated = False
        req.status = RequirementStatus.IN_PROGRESS
        req.escalation_status = "RESOLVED"
        req.escalation_resolved_at = datetime.now(timezone.utc)
        req.escalation_resolved_by_id = actor_id
        req.escalation_resolution_notes = data.resolution_notes

        # Append system message to thread
        actor_name = actor.full_name or actor.username if actor else "Authority"
        sys_msg = RequirementMessage(
            requirement_id=req.id,
            author_id=actor_id,
            content=f"[SYSTEM ACTIVITY: ESCALATION RESOLVED] Escalation resolved by {actor_name}. Notes: {data.resolution_notes}",
        )
        self.db.add(sys_msg)
        self.db.flush()

        # Notification triggers
        notify_users = set()
        if req.requester_id:
            notify_users.add(req.requester_id)
        if req.assignee_id:
            notify_users.add(req.assignee_id)

        for uid in notify_users:
            if uid != actor_id:
                self.notif_service.create_notification(
                    recipient_id=uid,
                    notification_type=NotificationType.REQUIREMENT,
                    title=f"Requirement Escalation Resolved: {req.title}",
                    message=f"The escalation on requirement '{req.title}' was resolved: {data.resolution_notes}",
                    related_resource_type="REQUIREMENT",
                    related_resource_id=req.id,
                )

        self.audit.log(
            action="REQUIREMENT_RESOLVE_ESCALATION",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"resolution_notes": data.resolution_notes},
        )
        logger.info(f"Resolved escalation on Requirement '{req.title}' (id={req.id})")
        return req

    def transition_status(self, req_id: UUID, data: RequirementTransitionRequest, actor_id: UUID) -> Requirement:
        req = self.get_requirement_by_id(req_id)
        actor = self.db.get(User, actor_id)
        old_status = req.status
        new_status = data.status

        # Prevent arbitrary jump if closed/completed
        terminal_statuses = [RequirementStatus.COMPLETED, RequirementStatus.CANCELLED, RequirementStatus.CLOSED]
        if old_status in terminal_statuses and new_status not in terminal_statuses:
            raise ValidationException(f"Cannot transition requirement from terminal state {old_status.value}")

        req.status = new_status
        if data.remarks:
            req.remarks = f"{req.remarks or ''}\n[Status: {new_status.value}] {data.remarks}".strip()

        # Append system message to thread
        actor_name = actor.full_name or actor.username if actor else "Staff"
        remarks_text = f" ({data.remarks})" if data.remarks else ""
        sys_msg = RequirementMessage(
            requirement_id=req.id,
            author_id=actor_id,
            content=f"[SYSTEM ACTIVITY: STATUS CHANGE] Status changed from {old_status.value} to {new_status.value} by {actor_name}{remarks_text}",
        )
        self.db.add(sys_msg)
        self.db.flush()

        # Notification on major lifecycle transitions
        notify_users = set()
        if req.requester_id:
            notify_users.add(req.requester_id)
        if req.assignee_id:
            notify_users.add(req.assignee_id)
        if req.responsible_poc_id:
            notify_users.add(req.responsible_poc_id)

        for uid in notify_users:
            if uid != actor_id:
                self.notif_service.create_notification(
                    recipient_id=uid,
                    notification_type=NotificationType.REQUIREMENT,
                    title=f"Requirement {new_status.value}: {req.title}",
                    message=f"Requirement '{req.title}' transitioned to {new_status.value}. Remarks: {data.remarks or 'N/A'}",
                    related_resource_type="REQUIREMENT",
                    related_resource_id=req.id,
                )

        self.audit.log(
            action="REQUIREMENT_STATUS_TRANSITION",
            resource_type="REQUIREMENT",
            resource_id=str(req.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"old_status": old_status.value, "new_status": new_status.value, "remarks": data.remarks},
        )
        return req

    def add_message(self, req_id: UUID, data: RequirementMessageCreate, author_id: UUID) -> RequirementMessage:
        req = self.get_requirement_by_id(req_id)
        author = self.db.get(User, author_id)
        message = RequirementMessage(
            requirement_id=req.id,
            author_id=author_id,
            content=data.content,
        )
        self.db.add(message)
        self.db.flush()

        # Notification to participants
        recipients = set()
        if req.requester_id:
            recipients.add(req.requester_id)
        if req.assignee_id:
            recipients.add(req.assignee_id)
        if req.responsible_poc_id:
            recipients.add(req.responsible_poc_id)

        for uid in recipients:
            if uid != author_id:
                self.notif_service.create_notification(
                    recipient_id=uid,
                    notification_type=NotificationType.REQUIREMENT,
                    title=f"New Message on Requirement: {req.title}",
                    message=f"{author.full_name or author.username if author else 'User'} commented on '{req.title}'.",
                    related_resource_type="REQUIREMENT",
                    related_resource_id=req.id,
                )

        self.audit.log(
            action="REQUIREMENT_MESSAGE_ADD",
            resource_type="REQUIREMENT_MESSAGE",
            resource_id=str(message.id),
            outcome="SUCCESS",
            actor_id=author_id,
            details={"requirement_id": str(req.id)},
        )
        return message

    def list_messages(self, req_id: UUID) -> List[RequirementMessage]:
        req = self.get_requirement_by_id(req_id)
        return list(
            self.db.scalars(
                select(RequirementMessage)
                .where(RequirementMessage.requirement_id == req.id)
                .options(selectinload(RequirementMessage.author))
                .order_by(RequirementMessage.created_at.asc())
            ).all()
        )
