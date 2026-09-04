"""
Master Tasks & Personal Work (My Work) Service Layer
Paradox Sports OMS - Phase 3 Core Operational System
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.communication import NotificationType
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.task import (
    Task,
    TaskComment,
    TaskHealth,
    TaskHistory,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.user import AccountStatus, User
from app.schemas.task import (
    TaskBlockRequest,
    TaskCreate,
    TaskEscalateRequest,
    TaskReassignRequest,
    TaskResolveEscalationRequest,
    TaskTransitionRequest,
    TaskUnblockRequest,
    TaskUpdate,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger("app.services.task")


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)


    def _validate_user_assignment(
        self,
        user_id: uuid.UUID,
        vertical_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> User:
        """Validates assignee exists, is ACTIVE, is assigned to the vertical, and adheres to hierarchy rules."""
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        if not user:
            raise EntityNotFoundException("User", str(user_id))

        if actor_id:
            actor = self.db.get(User, actor_id)
            if actor:
                from app.services.authority_service import AuthorityService
                auth_service = AuthorityService(self.db)
                auth_service.can_assign_task(actor, user, vertical_id)

        if user.account_status != AccountStatus.ACTIVE:
            raise ValidationException(
                f"Cannot assign task to user '{user.username}' because account status is {user.account_status.value}"
            )

        # Check user vertical assignment
        from app.services.authority_service import AuthorityService
        auth_service = AuthorityService(self.db)
        if not auth_service.is_executive_or_admin(user.id):
            stmt_uv = select(UserVertical).where(
                UserVertical.user_id == user_id,
                UserVertical.vertical_id == vertical_id,
            )
            if not self.db.scalar(stmt_uv):
                raise ValidationException(
                    f"Cannot assign task: User '{user.username}' is not assigned to the target vertical division"
                )

        return user

    def _validate_vertical(self, vertical_id: uuid.UUID) -> Vertical:
        """Validates that a vertical division exists and is ACTIVE."""
        stmt_v = select(Vertical).where(Vertical.id == vertical_id)
        vert = self.db.scalar(stmt_v)
        if not vert:
            raise EntityNotFoundException("Vertical", str(vertical_id))
        if vert.status != VerticalStatus.ACTIVE:
            raise ValidationException(f"Vertical '{vert.name}' is currently {vert.status.value}")
        return vert

    def _persist_single_task(
        self,
        vertical_id: uuid.UUID,
        assigned_to_id: Optional[uuid.UUID],
        actor_id: uuid.UUID,
        data: TaskCreate,
    ) -> Task:
        """Persists a single Task record with history, audit logging, and notifications."""
        task = Task(
            vertical_id=vertical_id,
            assigned_to_id=assigned_to_id,
            assigned_by_id=actor_id,
            title=data.title.strip(),
            description=data.description,
            task_type=data.task_type,
            priority=data.priority,
            status=TaskStatus.NOT_STARTED,
            completion_percentage=0,
            health=TaskHealth.ON_TRACK,
            deadline=data.deadline,
            blockers=data.blockers,
            remarks=data.remarks,
            evidence_link=data.evidence_link,
        )
        task.health = task.calculate_health()
        self.db.add(task)
        self.db.flush()

        # Task History entry
        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_CREATED",
            new_value={
                "title": task.title,
                "vertical_id": str(task.vertical_id),
                "assigned_to_id": str(task.assigned_to_id) if task.assigned_to_id else None,
                "priority": task.priority.value,
                "task_type": task.task_type.value,
                "status": task.status.value,
            },
        )
        self.db.add(history)

        # Audit Log
        self.audit.log(
            action="TASK_CREATE",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": task.title, "vertical_id": str(task.vertical_id)},
        )

        # Notification
        if task.assigned_to_id and task.assigned_to_id != actor_id:
            self.notif_service.create_notification(
                recipient_id=task.assigned_to_id,
                notification_type=NotificationType.TASK,
                title=f"Task Assigned: {task.title}",
                message=f"You have been assigned to task '{task.title}'.",
                related_resource_type="TASK",
                related_resource_id=task.id,
            )

        return task

    def create_task(self, data: TaskCreate, actor_id: uuid.UUID) -> Task:
        """Atomically creates one or more master tasks from Universal Selector or single payload."""
        from app.services.authority_service import AuthorityService
        auth_service = AuthorityService(self.db)
        actor = self.db.get(User, actor_id)

        # 1. Check if self task
        is_self = getattr(data, "is_self_task", False) or (data.assigned_to_id is not None and data.assigned_to_id == actor_id)
        if is_self:
            vert_id = data.vertical_id
            if not vert_id and data.vertical_ids:
                vert_id = data.vertical_ids[0]
            if not vert_id:
                actor_vids = auth_service.get_user_vertical_ids(actor_id)
                if actor_vids:
                    vert_id = actor_vids[0]
                elif auth_service.is_executive_or_admin(actor_id):
                    all_v = self.db.scalars(select(Vertical.id).where(Vertical.status == VerticalStatus.ACTIVE)).first()
                    vert_id = all_v
            if not vert_id:
                raise ValidationException("Please specify a target vertical division for your self task")

            self._validate_vertical(vert_id)
            if actor and not auth_service.has_vertical_access(actor_id, vert_id):
                raise ForbiddenException("You cannot create tasks in a vertical division you are not assigned to")

            self._validate_user_assignment(actor_id, vert_id, actor_id=actor_id)
            task = self._persist_single_task(vert_id, actor_id, actor_id, data)
            logger.info(f"Created Self Task '{task.title}' (id={task.id}) for user {actor_id}")
            return task

        # 2. Extract targets from Universal Selector or legacy fields
        raw_user_ids = getattr(data, "user_ids", None)
        target_user_ids = list(raw_user_ids) if raw_user_ids else []
        assigned_to_id = getattr(data, "assigned_to_id", None)
        if assigned_to_id and assigned_to_id not in target_user_ids:
            target_user_ids.append(assigned_to_id)

        raw_vertical_ids = getattr(data, "vertical_ids", None)
        target_vertical_ids = list(raw_vertical_ids) if raw_vertical_ids else []
        explicit_vertical_id = getattr(data, "vertical_id", None)
        if explicit_vertical_id and explicit_vertical_id not in target_vertical_ids:
            target_vertical_ids.append(explicit_vertical_id)

        # Handle audience dictionary if present
        aud = getattr(data, "audience", None)
        include_all = getattr(data, "include_all", False)
        role_ids = getattr(data, "role_ids", None)
        if aud and isinstance(aud, dict):
            if aud.get("include_all"):
                include_all = True
            for vid in aud.get("vertical_ids", []):
                vid_uuid = uuid.UUID(str(vid))
                if vid_uuid not in target_vertical_ids:
                    target_vertical_ids.append(vid_uuid)
            for uid in aud.get("user_ids", []):
                uid_uuid = uuid.UUID(str(uid))
                if uid_uuid not in target_user_ids:
                    target_user_ids.append(uid_uuid)
            if aud.get("role_ids"):
                role_ids = aud.get("role_ids")

        # Resolve audience if role_ids or include_all specified
        if include_all or role_ids:
            from app.services.audience_service import AudienceService
            from app.schemas.organization import AudienceResolveRequest
            aud_service = AudienceService(self.db)
            req = AudienceResolveRequest(
                all_users=include_all,
                vertical_ids=[str(v) for v in target_vertical_ids],
                role_ids=role_ids,
                user_ids=[str(u) for u in target_user_ids],
                usage="assignment",
            )
            resolved = aud_service.resolve_audience(req, actor=actor)
            for r_uid_str in resolved.user_ids:
                r_uid = uuid.UUID(r_uid_str)
                if r_uid not in target_user_ids:
                    target_user_ids.append(r_uid)

        # 3. Case A: Target users specified (Assignee-based tasks)
        if target_user_ids:
            created_tasks = []
            for uid in target_user_ids:
                target_user = self.db.get(User, uid)
                if not target_user:
                    raise EntityNotFoundException("User", str(uid))

                # Determine vertical for this user
                if explicit_vertical_id:
                    chosen_vert_id = explicit_vertical_id
                else:
                    user_vids = set(auth_service.get_user_vertical_ids(uid))
                    chosen_vert_id = None
                    for candidate_vid in target_vertical_ids:
                        if candidate_vid in user_vids or auth_service.is_executive_or_admin(uid):
                            chosen_vert_id = candidate_vid
                            break
                    if not chosen_vert_id:
                        if user_vids:
                            chosen_vert_id = list(user_vids)[0]
                        elif target_vertical_ids and auth_service.is_executive_or_admin(uid):
                            chosen_vert_id = target_vertical_ids[0]
                        elif auth_service.is_executive_or_admin(actor_id) and target_vertical_ids:
                            chosen_vert_id = target_vertical_ids[0]

                if not chosen_vert_id:
                    raise ValidationException(
                        f"Cannot assign task: User '{target_user.username}' is not assigned to any target vertical division"
                    )

                self._validate_vertical(chosen_vert_id)
                if actor and not auth_service.has_vertical_access(actor_id, chosen_vert_id):
                    raise ForbiddenException("You cannot create tasks in a vertical division you are not assigned to")

                self._validate_user_assignment(uid, chosen_vert_id, actor_id=actor_id)
                t = self._persist_single_task(chosen_vert_id, uid, actor_id, data)
                created_tasks.append(t)

            logger.info(f"Created {len(created_tasks)} tasks for users: {target_user_ids}")
            return created_tasks[0]

        # 4. Case B: Only verticals specified (Unassigned tasks in each vertical)
        if target_vertical_ids:
            created_tasks = []
            for vid in target_vertical_ids:
                self._validate_vertical(vid)
                if actor and not auth_service.has_vertical_access(actor_id, vid):
                    raise ForbiddenException("You cannot create tasks in a vertical division you are not assigned to")

                t = self._persist_single_task(vid, None, actor_id, data)
                created_tasks.append(t)

            logger.info(f"Created {len(created_tasks)} unassigned tasks in verticals: {target_vertical_ids}")
            return created_tasks[0]

        # 5. If no target specified at all
        raise ValidationException("Please select at least one vertical division or user assignment target")


    def get_task_by_id(self, task_id: uuid.UUID) -> Task:
        """Retrieves task by UUID with preloaded relationships."""
        stmt = (
            select(Task)
            .where(Task.id == task_id)
            .options(
                selectinload(Task.vertical),
                selectinload(Task.assigned_to),
                selectinload(Task.assigned_by),
                selectinload(Task.comments).selectinload(TaskComment.author),
                selectinload(Task.history_entries).selectinload(TaskHistory.actor),
            )
        )
        task = self.db.scalar(stmt)
        if not task:
            raise EntityNotFoundException("Task", str(task_id))
        return task

    def list_tasks(
        self,
        vertical_id: Optional[uuid.UUID] = None,
        assigned_to_id: Optional[uuid.UUID] = None,
        created_by_id: Optional[uuid.UUID] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        task_type: Optional[TaskType] = None,
        health: Optional[TaskHealth] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        actor: Optional[User] = None,
    ) -> Tuple[List[Task], int]:
        """Lists tasks with filters, search, pagination, and caller visibility scoping."""
        stmt = select(Task).options(
            selectinload(Task.vertical),
            selectinload(Task.assigned_to),
            selectinload(Task.assigned_by),
        )

        # Scoping based on caller authority
        if actor:
            from app.services.authority_service import AuthorityService
            auth_service = AuthorityService(self.db)
            if not auth_service.is_executive_or_admin(actor.id):
                actor_vids = set(auth_service.get_user_vertical_ids(actor.id))
                actor_level = auth_service.get_user_operational_level(actor.id) or 1
                if actor_level <= 1:
                    # Volunteers can see tasks in their verticals where they are either assignee or creator
                    stmt = stmt.where(
                        Task.vertical_id.in_(actor_vids),
                        or_(Task.assigned_to_id == actor.id, Task.assigned_by_id == actor.id),
                    )
                else:
                    # Coordinators / Super Coordinators can see all tasks in their vertical divisions
                    stmt = stmt.where(Task.vertical_id.in_(actor_vids))

        if vertical_id:
            stmt = stmt.where(Task.vertical_id == vertical_id)
        if assigned_to_id:
            stmt = stmt.where(Task.assigned_to_id == assigned_to_id)
        if created_by_id:
            stmt = stmt.where(Task.assigned_by_id == created_by_id)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        if health:
            stmt = stmt.where(Task.health == health)
        if search:
            stmt = stmt.where(
                or_(
                    Task.title.ilike(f"%{search}%"),
                    Task.description.ilike(f"%{search}%"),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Order by created_at desc
        stmt = stmt.order_by(desc(Task.created_at)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())

        return items, total

    def list_my_work(
        self,
        user_id: uuid.UUID,
        status_filter: Optional[str] = None,  # active, overdue, blocked, completed, upcoming
        priority: Optional[TaskPriority] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Task], int]:
        """
        Retrieves tasks assigned strictly to the authenticated user.
        Never allows client to query other users' work view.
        """
        stmt = (
            select(Task)
            .where(Task.assigned_to_id == user_id)
            .options(
                selectinload(Task.vertical),
                selectinload(Task.assigned_to),
                selectinload(Task.assigned_by),
            )
        )

        now = datetime.now(timezone.utc)
        if status_filter == "active":
            stmt = stmt.where(Task.status.in_([TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS]))
        elif status_filter == "completed":
            stmt = stmt.where(Task.status == TaskStatus.COMPLETED)
        elif status_filter == "blocked":
            stmt = stmt.where(Task.status == TaskStatus.BLOCKED)
        elif status_filter == "overdue":
            stmt = stmt.where(Task.deadline < now, Task.status != TaskStatus.COMPLETED)
        elif status_filter == "upcoming":
            stmt = stmt.where(Task.deadline >= now, Task.status != TaskStatus.COMPLETED)

        if priority:
            stmt = stmt.where(Task.priority == priority)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(Task.deadline.asc().nullslast(), desc(Task.priority)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())

        return items, total

    def update_task(self, task_id: uuid.UUID, data: TaskUpdate, actor_id: uuid.UUID) -> Task:
        """Updates general task fields, recalculates health, and records history."""
        task = self.get_task_by_id(task_id)
        prev_state = {
            "title": task.title,
            "priority": task.priority.value,
            "completion_percentage": task.completion_percentage,
            "deadline": task.deadline.isoformat() if task.deadline else None,
        }

        if data.title is not None:
            task.title = data.title.strip()
        if data.description is not None:
            task.description = data.description
        if data.task_type is not None:
            task.task_type = data.task_type
        if data.priority is not None:
            task.priority = data.priority
        if data.deadline is not None:
            task.deadline = data.deadline
        if data.completion_percentage is not None:
            task.completion_percentage = data.completion_percentage
        if data.blockers is not None:
            task.blockers = data.blockers
        if data.remarks is not None:
            task.remarks = data.remarks
        if data.latest_update is not None:
            task.latest_update = data.latest_update
        if data.evidence_link is not None:
            task.evidence_link = data.evidence_link
        if data.deficiency is not None:
            task.deficiency = data.deficiency

        task.health = task.calculate_health()
        self.db.flush()

        # Record History
        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_UPDATED",
            previous_value=prev_state,
            new_value={
                "title": task.title,
                "priority": task.priority.value,
                "completion_percentage": task.completion_percentage,
                "deadline": task.deadline.isoformat() if task.deadline else None,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_UPDATE",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": task.title},
        )

        self.db.flush()
        return task

    def transition_status(
        self,
        task_id: uuid.UUID,
        transition: TaskTransitionRequest,
        actor_id: uuid.UUID,
    ) -> Task:
        """Validates and applies atomic status transitions with lifecycle rules."""
        task = self.get_task_by_id(task_id)
        prev_status = task.status
        new_status = transition.status

        # Validate completion percentage logic
        if new_status == TaskStatus.COMPLETED:
            task.completion_percentage = 100
            task.completed_on = datetime.now(timezone.utc)
            task.health = TaskHealth.COMPLETE
        elif new_status == TaskStatus.NOT_STARTED:
            task.completion_percentage = 0
            task.completed_on = None
        elif new_status == TaskStatus.IN_PROGRESS:
            if transition.completion_percentage is not None:
                task.completion_percentage = transition.completion_percentage
            elif task.completion_percentage == 0:
                task.completion_percentage = 10
            task.completed_on = None
        elif new_status == TaskStatus.BLOCKED:
            if transition.blockers:
                task.blockers = transition.blockers
            task.health = TaskHealth.BLOCKED
        elif new_status == TaskStatus.CANCELLED:
            task.completed_on = None

        if transition.remarks:
            task.remarks = transition.remarks

        task.status = new_status
        task.health = task.calculate_health()
        self.db.flush()

        # Record History
        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="STATUS_TRANSITION",
            previous_value={"status": prev_status.value},
            new_value={
                "status": new_status.value,
                "completion_percentage": task.completion_percentage,
                "health": task.health.value,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_STATUS_TRANSITION",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"from": prev_status.value, "to": new_status.value},
        )

        self.db.flush()
        return task

    def assign_task(
        self,
        task_id: uuid.UUID,
        assigned_to_id: Optional[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> Task:
        """Assigns task to an active user within the task's vertical division."""
        task = self.get_task_by_id(task_id)
        prev_assignee = task.assigned_to_id

        if assigned_to_id:
            task.assigned_to = self._validate_user_assignment(assigned_to_id, task.vertical_id, actor_id=actor_id)
        else:
            task.assigned_to = None

        task.assigned_to_id = assigned_to_id
        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_ASSIGNED",
            previous_value={"assigned_to_id": str(prev_assignee) if prev_assignee else None},
            new_value={"assigned_to_id": str(assigned_to_id) if assigned_to_id else None},
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_ASSIGN",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"assigned_to_id": str(assigned_to_id) if assigned_to_id else None},
        )

        # Notification trigger
        if assigned_to_id and assigned_to_id != actor_id:
            self.notif_service.create_notification(
                recipient_id=assigned_to_id,
                notification_type=NotificationType.TASK,
                title=f"Task Assigned: {task.title}",
                message=f"You have been assigned to task '{task.title}'.",
                related_resource_type="TASK",
                related_resource_id=task.id,
            )

        self.db.flush()
        return task

    def reassign_task(
        self,
        task_id: uuid.UUID,
        data: TaskReassignRequest,
        actor_id: uuid.UUID,
    ) -> Task:
        """
        Reassigns task to a new active user within the task's vertical division.
        Records history and audit log.
        """
        task = self.get_task_by_id(task_id)
        prev_assignee = task.assigned_to_id

        # Validate target user is active and belongs to task's vertical
        new_assignee = self._validate_user_assignment(data.new_assigned_to_id, task.vertical_id, actor_id=actor_id)

        task.assigned_to_id = data.new_assigned_to_id
        task.assigned_to = new_assignee
        if data.remarks:
            task.remarks = data.remarks

        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_REASSIGNED",
            previous_value={"assigned_to_id": str(prev_assignee) if prev_assignee else None},
            new_value={
                "assigned_to_id": str(data.new_assigned_to_id),
                "assigned_to_username": new_assignee.username,
                "remarks": data.remarks,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_REASSIGN",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "previous_assigned_to_id": str(prev_assignee) if prev_assignee else None,
                "new_assigned_to_id": str(data.new_assigned_to_id),
                "new_assigned_to_username": new_assignee.username,
            },
        )

        # Notification trigger
        if data.new_assigned_to_id and data.new_assigned_to_id != actor_id:
            self.notif_service.create_notification(
                recipient_id=data.new_assigned_to_id,
                notification_type=NotificationType.TASK,
                title=f"Task Reassigned: {task.title}",
                message=f"Task '{task.title}' has been reassigned to you.",
                related_resource_type="TASK",
                related_resource_id=task.id,
            )

        self.db.flush()
        logger.info(f"Reassigned Task {task.id} to '{new_assignee.username}'")
        return task


    def escalate_task(
        self,
        task_id: uuid.UUID,
        data: TaskEscalateRequest,
        actor_id: uuid.UUID,
    ) -> Task:
        """
        Escalates a task to a designated authority or higher operational level.
        """
        task = self.get_task_by_id(task_id)
        prev_escalated = task.is_escalated

        task.is_escalated = True
        task.escalated_to_id = data.escalated_to_id
        task.escalated_by_id = actor_id
        task.escalation_reason = data.reason.strip()
        task.escalated_at = datetime.now(timezone.utc)
        task.escalation_status = "PENDING"
        if data.remarks:
            task.remarks = data.remarks

        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_ESCALATED",
            previous_value={"is_escalated": prev_escalated},
            new_value={
                "is_escalated": True,
                "escalated_to_id": str(data.escalated_to_id) if data.escalated_to_id else None,
                "reason": task.escalation_reason,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_ESCALATE",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"reason": task.escalation_reason, "escalated_to_id": str(data.escalated_to_id) if data.escalated_to_id else None},
        )

        self.db.flush()
        logger.info(f"Escalated Task {task.id}: {task.escalation_reason}")
        return task

    def resolve_escalation(
        self,
        task_id: uuid.UUID,
        data: TaskResolveEscalationRequest,
        actor_id: uuid.UUID,
    ) -> Task:
        """
        Resolves an active escalation on a task.
        """
        task = self.get_task_by_id(task_id)
        if not task.is_escalated:
            raise ValidationException("Task is not currently marked as escalated")

        task.is_escalated = False
        task.escalation_status = "RESOLVED"
        task.escalation_resolution = data.resolution.strip()
        task.escalation_resolved_at = datetime.now(timezone.utc)
        if data.remarks:
            task.remarks = data.remarks

        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_ESCALATION_RESOLVED",
            previous_value={"escalation_status": "PENDING"},
            new_value={
                "escalation_status": "RESOLVED",
                "resolution": task.escalation_resolution,
            },
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_RESOLVE_ESCALATION",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"resolution": task.escalation_resolution},
        )

        self.db.flush()
        logger.info(f"Resolved escalation on Task {task.id}")
        return task

    def block_task(
        self,
        task_id: uuid.UUID,
        blocker_description: str,
        actor_id: uuid.UUID,
    ) -> Task:
        """
        Marks a task as BLOCKED with structured blocker details.
        """
        task = self.get_task_by_id(task_id)
        prev_status = task.status

        task.status = TaskStatus.BLOCKED
        task.health = TaskHealth.BLOCKED
        task.blockers = blocker_description.strip()
        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_BLOCKED",
            previous_value={"status": prev_status.value},
            new_value={"status": TaskStatus.BLOCKED.value, "blockers": task.blockers},
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_BLOCK",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"blockers": task.blockers},
        )

        self.db.flush()
        logger.info(f"Blocked Task {task.id}: {task.blockers}")
        return task

    def unblock_task(
        self,
        task_id: uuid.UUID,
        resolution: Optional[str],
        actor_id: uuid.UUID,
    ) -> Task:
        """
        Unblocks a task, transitioning it back to IN_PROGRESS.
        """
        task = self.get_task_by_id(task_id)
        prev_blockers = task.blockers

        task.status = TaskStatus.IN_PROGRESS
        task.blockers = None
        if resolution:
            task.latest_update = f"Unblocked: {resolution.strip()}"
        task.health = task.calculate_health()
        self.db.flush()

        history = TaskHistory(
            task_id=task.id,
            actor_id=actor_id,
            action="TASK_UNBLOCKED",
            previous_value={"status": TaskStatus.BLOCKED.value, "blockers": prev_blockers},
            new_value={"status": TaskStatus.IN_PROGRESS.value, "resolution": resolution},
        )
        self.db.add(history)

        self.audit.log(
            action="TASK_UNBLOCK",
            resource_type="TASK",
            resource_id=str(task.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"resolution": resolution},
        )

        self.db.flush()
        logger.info(f"Unblocked Task {task.id}")
        return task

    def add_comment(self, task_id: uuid.UUID, author_id: uuid.UUID, content: str) -> TaskComment:
        """Adds a comment to the task."""
        task = self.get_task_by_id(task_id)
        comment = TaskComment(
            task_id=task.id,
            author_id=author_id,
            content=content.strip(),
        )
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_comments(self, task_id: uuid.UUID) -> List[TaskComment]:
        """Lists comments for a task."""
        stmt = (
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .options(selectinload(TaskComment.author))
            .order_by(TaskComment.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_history(self, task_id: uuid.UUID) -> List[TaskHistory]:
        """Lists immutable history for a task."""
        stmt = (
            select(TaskHistory)
            .where(TaskHistory.task_id == task_id)
            .options(selectinload(TaskHistory.actor))
            .order_by(TaskHistory.timestamp.desc())
        )
        return list(self.db.scalars(stmt).all())
