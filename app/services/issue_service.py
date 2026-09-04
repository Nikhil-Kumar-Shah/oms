"""
Issue & Escalation Register Service Layer
Paradox Sports OMS - Phase 3 Core Operational System
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.issue import (
    Issue,
    IssueAssignee,
    IssueComment,
    IssueHistory,
    IssueSensitivity,
    IssueStatus,
)
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.user import AccountStatus, User
from app.schemas.issue import IssueCreate, IssueEscalateRequest, IssueTransitionRequest, IssueUpdate
from app.schemas.organization import AudienceResolveRequest
from app.services.audit_service import AuditService

logger = get_logger("app.services.issue")


class IssueService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def _can_access_confidential_issue(self, issue: Issue, user: User) -> bool:
        """Determines if the user is authorized to access a confidential issue."""
        if issue.sensitivity != IssueSensitivity.CONFIDENTIAL:
            return True

        is_assigned = (
            issue.assigned_to_id == user.id
            or any(ia.user_id == user.id for ia in getattr(issue, "issue_assignees", []))
        )
        if issue.raised_by_id == user.id or is_assigned:
            return True

        from app.services.rbac_service import RbacService
        rbac = RbacService(self.db)
        perms = rbac.get_effective_permissions(user.id)
        if "issues.confidential.read" in perms or "ADMIN" in [r.name for r in rbac.get_user_roles(user.id)]:
            return True

        return False

    def create_issue(self, data: IssueCreate, actor_id: uuid.UUID) -> Issue:
        """Creates an issue in the register with multi-assignee resolution, permissions, and audit logging."""
        actor = self.db.get(User, actor_id)
        if not actor:
            raise EntityNotFoundException("User", str(actor_id))

        from app.services.authority_service import AuthorityService
        auth = AuthorityService(self.db)
        is_exec_or_admin = auth.is_executive_or_admin(actor_id)
        user_vert_ids = set(auth.get_user_vertical_ids(actor_id))

        # 1. Audience / Vertical Scope Resolution & Permission Checks
        target_vertical_id = data.vertical_id
        if not target_vertical_id and data.vertical_ids:
            target_vertical_id = data.vertical_ids[0]

        if not target_vertical_id and not data.all_users:
            raise ValidationException("Audience / Scope is required. Please select a vertical division.")

        if target_vertical_id:
            vert = self.db.scalar(select(Vertical).where(Vertical.id == target_vertical_id))
            if not vert or vert.status != VerticalStatus.ACTIVE:
                raise ValidationException("Target vertical does not exist or is inactive")

            # Cross-vertical check for non-executives
            if not is_exec_or_admin and target_vertical_id not in user_vert_ids:
                raise ForbiddenException("Cross-vertical violation: You cannot raise issues outside your assigned vertical division")

        if data.vertical_ids and not is_exec_or_admin:
            for vid in data.vertical_ids:
                if vid not in user_vert_ids:
                    raise ForbiddenException("Cross-vertical violation: You cannot raise issues outside your assigned vertical division")

        # 2. Assignee / Responsible Users Resolution
        from app.services.audience_service import AudienceService
        audience_service = AudienceService(self.db)

        resolved_assignee_ids: set[uuid.UUID] = set()

        # Legacy single assignee support
        if data.assigned_to_id:
            stmt_u = select(User).where(User.id == data.assigned_to_id)
            assignee = self.db.scalar(stmt_u)
            if not assignee or assignee.account_status != AccountStatus.ACTIVE:
                raise ValidationException("Assigned user does not exist or is inactive")
            resolved_assignee_ids.add(data.assigned_to_id)

        # Multi-assignee resolution using AudienceService
        if data.assignee_all_users or data.assignee_vertical_ids or data.assignee_role_ids or data.assignee_user_ids:
            aud_req = AudienceResolveRequest(
                all_users=data.assignee_all_users or False,
                vertical_ids=data.assignee_vertical_ids or [],
                role_ids=data.assignee_role_ids or [],
                user_ids=data.assignee_user_ids or [],
                usage="assignment",
            )
            aud_res = audience_service.resolve_audience(aud_req, actor)
            resolved_assignee_ids.update(aud_res.user_ids)

        primary_assignee_id = next(iter(resolved_assignee_ids)) if resolved_assignee_ids else None

        # 3. Create Issue Model
        issue = Issue(
            vertical_id=target_vertical_id,
            title=data.title.strip(),
            description=data.description.strip(),
            event_reference=data.event_reference,
            raised_by_id=actor_id,
            assigned_to_id=primary_assignee_id,
            sensitivity=data.sensitivity,
            status=IssueStatus.OPEN,
            action_required=data.action_required,
            deadline=data.deadline,
            evidence_link=data.evidence_link,
            remarks=data.remarks,
        )
        self.db.add(issue)
        self.db.flush()

        # 4. Insert into issue_assignees junction table
        if resolved_assignee_ids:
            for uid in resolved_assignee_ids:
                self.db.add(IssueAssignee(issue_id=issue.id, user_id=uid))
            self.db.flush()

        # 5. History & Audit Logging
        history = IssueHistory(
            issue_id=issue.id,
            actor_id=actor_id,
            action="ISSUE_RAISED",
            details={
                "title": issue.title,
                "vertical_id": str(issue.vertical_id) if issue.vertical_id else None,
                "sensitivity": issue.sensitivity.value,
                "status": issue.status.value,
                "assignee_count": len(resolved_assignee_ids),
            },
        )
        self.db.add(history)

        self.audit.log(
            action="ISSUE_CREATE",
            resource_type="ISSUE",
            resource_id=str(issue.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "title": issue.title,
                "sensitivity": issue.sensitivity.value,
                "assignee_count": len(resolved_assignee_ids),
            },
        )

        # 6. Dispatch Notifications to assignees
        recipient_ids = [uid for uid in resolved_assignee_ids if uid != actor_id]
        if recipient_ids:
            try:
                from app.services.notification_service import NotificationService
                notif_service = NotificationService(self.db)
                notif_service.create_batch_notifications(
                    recipient_ids=recipient_ids,
                    title=f"New Issue Assigned: {issue.title}",
                    message=f"You have been assigned to operational issue '{issue.title}' raised by {actor.username}.",
                    related_resource_type="ISSUE",
                    related_resource_id=issue.id,
                )
            except Exception as ex:
                logger.warning(f"Failed to dispatch issue assignment notifications: {ex}")

        self.db.flush()
        logger.info(f"Created Issue '{issue.title}' (id={issue.id}, assignees={len(resolved_assignee_ids)})")
        return issue

    def get_issue_by_id(self, issue_id: uuid.UUID, current_user: Optional[User] = None) -> Issue:
        """Retrieves issue by UUID and enforces sensitivity authorization."""
        stmt = (
            select(Issue)
            .where(Issue.id == issue_id)
            .options(
                selectinload(Issue.vertical),
                selectinload(Issue.raised_by),
                selectinload(Issue.assigned_to),
                selectinload(Issue.issue_assignees).selectinload(IssueAssignee.user),
                selectinload(Issue.history_entries).selectinload(IssueHistory.actor),
            )
        )
        issue = self.db.scalar(stmt)
        if not issue:
            raise EntityNotFoundException("Issue", str(issue_id))

        if current_user:
            from app.services.authority_service import AuthorityService
            auth_service = AuthorityService(self.db)
            if not auth_service.is_executive_or_admin(current_user.id):
                user_vids = auth_service.get_user_vertical_ids(current_user.id)
                is_assigned = (
                    issue.assigned_to_id == current_user.id
                    or any(ia.user_id == current_user.id for ia in getattr(issue, "issue_assignees", []))
                )
                has_access = (
                    (issue.vertical_id and issue.vertical_id in user_vids)
                    or issue.raised_by_id == current_user.id
                    or is_assigned
                )
                if not has_access:
                    raise ForbiddenException("You do not have authorization to view this issue")

            if not self._can_access_confidential_issue(issue, current_user):
                raise ForbiddenException("Access denied: You do not have permission to view this confidential issue")

        return issue

    def list_issues(
        self,
        current_user: User,
        vertical_id: Optional[uuid.UUID] = None,
        status: Optional[IssueStatus] = None,
        sensitivity: Optional[IssueSensitivity] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Issue], int]:
        """Lists issues with filters, vertical scoping, and sensitivity filtering."""
        stmt = select(Issue).options(
            selectinload(Issue.vertical),
            selectinload(Issue.raised_by),
            selectinload(Issue.assigned_to),
            selectinload(Issue.issue_assignees).selectinload(IssueAssignee.user),
        )

        from app.services.authority_service import AuthorityService
        auth_service = AuthorityService(self.db)
        if not auth_service.is_executive_or_admin(current_user.id):
            user_vids = auth_service.get_user_vertical_ids(current_user.id)
            if not user_vids:
                return [], 0
            if vertical_id:
                if vertical_id not in user_vids:
                    return [], 0
                stmt = stmt.where(Issue.vertical_id == vertical_id)
            else:
                stmt = stmt.where(
                    or_(
                        Issue.vertical_id.in_(user_vids),
                        Issue.raised_by_id == current_user.id,
                        Issue.assigned_to_id == current_user.id,
                        Issue.issue_assignees.any(IssueAssignee.user_id == current_user.id),
                    )
                )
        elif vertical_id:
            stmt = stmt.where(Issue.vertical_id == vertical_id)

        if status:
            stmt = stmt.where(Issue.status == status)
        if sensitivity:
            stmt = stmt.where(Issue.sensitivity == sensitivity)

        from app.services.rbac_service import RbacService
        rbac = RbacService(self.db)
        perms = rbac.get_effective_permissions(current_user.id)
        roles = [r.name for r in rbac.get_user_roles(current_user.id)]
        can_view_all_confidential = "issues.confidential.read" in perms or "ADMIN" in roles

        if not can_view_all_confidential:
            # Filter out CONFIDENTIAL issues unless raised by or assigned to current user
            stmt = stmt.where(
                or_(
                    Issue.sensitivity != IssueSensitivity.CONFIDENTIAL,
                    Issue.raised_by_id == current_user.id,
                    Issue.assigned_to_id == current_user.id,
                    Issue.issue_assignees.any(IssueAssignee.user_id == current_user.id),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(Issue.date_raised)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())

        return items, total


    def update_issue(self, issue_id: uuid.UUID, data: IssueUpdate, actor_id: uuid.UUID) -> Issue:
        """Updates issue attributes and records history."""
        issue = self.get_issue_by_id(issue_id)

        if data.title is not None:
            issue.title = data.title.strip()
        if data.description is not None:
            issue.description = data.description.strip()
        if data.event_reference is not None:
            issue.event_reference = data.event_reference
        if data.assigned_to_id is not None:
            issue.assigned_to_id = data.assigned_to_id
        if data.sensitivity is not None:
            issue.sensitivity = data.sensitivity
        if data.action_required is not None:
            issue.action_required = data.action_required
        if data.deadline is not None:
            issue.deadline = data.deadline
        if data.evidence_link is not None:
            issue.evidence_link = data.evidence_link
        if data.remarks is not None:
            issue.remarks = data.remarks

        self.db.flush()

        history = IssueHistory(
            issue_id=issue.id,
            actor_id=actor_id,
            action="ISSUE_UPDATED",
            details={"title": issue.title, "sensitivity": issue.sensitivity.value},
        )
        self.db.add(history)

        self.audit.log(
            action="ISSUE_UPDATE",
            resource_type="ISSUE",
            resource_id=str(issue.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": issue.title},
        )

        self.db.flush()
        return issue

    def transition_status(
        self,
        issue_id: uuid.UUID,
        transition: IssueTransitionRequest,
        actor_id: uuid.UUID,
    ) -> Issue:
        """Transitions issue status with resolution tracking."""
        issue = self.get_issue_by_id(issue_id)
        prev_status = issue.status
        new_status = transition.status

        if new_status in [IssueStatus.RESOLVED, IssueStatus.CLOSED]:
            if transition.resolution:
                issue.resolution = transition.resolution
            issue.resolution_date = datetime.now(timezone.utc)
            # Shut down active escalation targets and actions when resolved/closed
            issue.escalation_target = None
            issue.escalation_action = None

            # Automatically dismiss / mark as read any unread notifications alerting users to this issue
            try:
                from app.models.communication import Notification, NotificationReadStatus
                active_notifs = self.db.scalars(
                    select(Notification).where(
                        Notification.related_resource_type == "ISSUE",
                        Notification.related_resource_id == issue.id,
                        Notification.read_status == NotificationReadStatus.UNREAD,
                    )
                ).all()
                now_ts = datetime.now(timezone.utc)
                for n in active_notifs:
                    n.read_status = NotificationReadStatus.READ
                    n.read_at = now_ts
            except Exception as ex:
                logger.warning(f"Failed to clear notifications for resolved issue: {ex}")
        elif new_status == IssueStatus.OPEN:
            issue.resolution_date = None

        if transition.remarks:
            issue.remarks = transition.remarks

        issue.status = new_status
        self.db.flush()

        history = IssueHistory(
            issue_id=issue.id,
            actor_id=actor_id,
            action="STATUS_TRANSITION",
            details={
                "from": prev_status.value,
                "to": new_status.value,
                "resolution": issue.resolution,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="ISSUE_STATUS_TRANSITION",
            resource_type="ISSUE",
            resource_id=str(issue.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"from": prev_status.value, "to": new_status.value},
        )

        self.db.flush()
        return issue

    def escalate_issue(
        self,
        issue_id: uuid.UUID,
        data: IssueEscalateRequest,
        actor_id: uuid.UUID,
    ) -> Issue:
        """Escalates issue to a higher authority."""
        issue = self.get_issue_by_id(issue_id)
        prev_status = issue.status

        issue.status = IssueStatus.ESCALATED
        issue.escalation_target = data.escalation_target.strip()
        issue.escalation_action = data.escalation_action.strip()
        if data.deadline:
            issue.deadline = data.deadline
        if data.remarks:
            issue.remarks = data.remarks

        self.db.flush()

        history = IssueHistory(
            issue_id=issue.id,
            actor_id=actor_id,
            action="ISSUE_ESCALATED",
            details={
                "from": prev_status.value,
                "to": IssueStatus.ESCALATED.value,
                "escalation_target": issue.escalation_target,
                "escalation_action": issue.escalation_action,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="ISSUE_ESCALATE",
            resource_type="ISSUE",
            resource_id=str(issue.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"escalation_target": issue.escalation_target},
        )

        self.db.flush()
        return issue

    def list_history(self, issue_id: uuid.UUID) -> List[IssueHistory]:
        """Lists immutable history for an issue."""
        stmt = (
            select(IssueHistory)
            .where(IssueHistory.issue_id == issue_id)
            .options(selectinload(IssueHistory.actor))
            .order_by(IssueHistory.timestamp.desc())
        )
        return list(self.db.scalars(stmt).all())

    def add_comment(self, issue_id: uuid.UUID, author_id: uuid.UUID, content: str) -> "IssueComment":
        """Adds a comment to the issue."""
        issue = self.get_issue_by_id(issue_id)
        comment = IssueComment(
            issue_id=issue.id,
            author_id=author_id,
            content=content.strip(),
        )
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_comments(self, issue_id: uuid.UUID) -> List["IssueComment"]:
        """Lists comments for an issue."""
        stmt = (
            select(IssueComment)
            .where(IssueComment.issue_id == issue_id)
            .options(selectinload(IssueComment.author))
            .order_by(IssueComment.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
