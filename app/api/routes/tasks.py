"""
Master Tasks & Personal Work (My Work) API Endpoints
Paradox Sports OMS - Phase 3 Core Operational System
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.models.task import TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import User
from app.schemas.task import (
    TaskAssignRequest,
    TaskBlockRequest,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    SelfTaskCreate,
    TaskEscalateRequest,
    TaskHistoryResponse,
    TaskListResponse,
    TaskReassignRequest,
    TaskResolveEscalationRequest,
    TaskResponse,
    TaskTransitionRequest,
    TaskUnblockRequest,
    TaskUpdate,
)
from app.services.task_service import TaskService

tasks_router = APIRouter(prefix="", tags=["Master Tasks & My Work"])


def _format_task_response(task) -> TaskResponse:
    """Helper to convert task model to response schema with preloaded attributes."""
    return TaskResponse(
        id=task.id,
        vertical_id=task.vertical_id,
        vertical_name=task.vertical.name if task.vertical else None,
        assigned_to_id=task.assigned_to_id,
        assigned_to_username=task.assigned_to.username if task.assigned_to else None,
        assigned_to_name=task.assigned_to.full_name if task.assigned_to else None,
        assigned_by_id=task.assigned_by_id,
        assigned_by_username=task.assigned_by.username if task.assigned_by else None,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        priority=task.priority,
        status=task.status,
        completion_percentage=task.completion_percentage,
        health=task.health,
        date_assigned=task.date_assigned,
        deadline=task.deadline,
        completed_on=task.completed_on,
        blockers=task.blockers,
        remarks=task.remarks,
        latest_update=task.latest_update,
        evidence_link=task.evidence_link,
        deficiency=task.deficiency,
        is_escalated=task.is_escalated,
        escalated_to_id=task.escalated_to_id,
        escalated_to_username=task.escalated_to.username if task.escalated_to else None,
        escalation_reason=task.escalation_reason,
        escalated_at=task.escalated_at,
        escalation_status=task.escalation_status,
        escalation_resolution=task.escalation_resolution,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# -----------------------------------------------------------------------------
# My Work View
# -----------------------------------------------------------------------------

@tasks_router.get("/my-work", response_model=TaskListResponse)
async def get_my_work(
    status_filter: Optional[str] = Query(None, description="Filter: active, overdue, blocked, completed, upcoming"),
    priority: Optional[TaskPriority] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves personal operational tasks assigned strictly to the authenticated user.
    Never accepts client-supplied user_id for identity resolution.
    """
    service = TaskService(db)
    items, total = service.list_my_work(
        user_id=current_user.id,
        status_filter=status_filter,
        priority=priority,
        skip=skip,
        limit=limit,
    )
    return TaskListResponse(total=total, items=[_format_task_response(t) for t in items])


# -----------------------------------------------------------------------------
# Master Tasks Endpoints
# -----------------------------------------------------------------------------

@tasks_router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    vertical_id: Optional[uuid.UUID] = Query(None),
    assigned_to_id: Optional[uuid.UUID] = Query(None),
    created_by_id: Optional[uuid.UUID] = Query(None, alias="assigned_by_id"),
    scope: Optional[str] = Query(None, description="Filter scope: all, my_tasks, created_by_me"),
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    health: Optional[TaskHealth] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("tasks.read")),
    db: Session = Depends(get_db),
):
    """
    Lists operational tasks with multi-dimensional filtering and server-authoritative caller visibility scoping.
    - scope='my_tasks': tasks where assigned_to_id == current_user.id
    - scope='created_by_me': tasks where assigned_by_id == current_user.id
    - scope='all' or omitted: all tasks within caller's authorized vertical scope
    """
    # If accessing unscoped global master tasks register, enforce executive access
    if not scope and not vertical_id and not assigned_to_id and not created_by_id:
        from app.services.authority_service import AuthorityService
        from app.core.exceptions import ForbiddenException
        authority_service = AuthorityService(db)
        if not authority_service.can_access_master_tasks_register(current_user.id):
            raise ForbiddenException(
                "Access to global Master Tasks register is restricted to executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN). Use My Work for operational tasks."
            )

    if scope == "my_tasks":
        assigned_to_id = current_user.id
    elif scope == "created_by_me":
        created_by_id = current_user.id

    service = TaskService(db)
    items, total = service.list_tasks(
        vertical_id=vertical_id,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        status=status,
        priority=priority,
        task_type=task_type,
        health=health,
        search=search,
        skip=skip,
        limit=limit,
        actor=current_user,
    )
    return TaskListResponse(total=total, items=[_format_task_response(t) for t in items])


@tasks_router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(require_permission("tasks.create")),
    db: Session = Depends(get_db),
):
    """Creates a new master task or self-assigned task."""
    service = TaskService(db)
    task = service.create_task(data, actor_id=current_user.id)
    db.commit()
    # Reload for relationship response
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/self", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_self_task(
    data: SelfTaskCreate,
    current_user: User = Depends(require_permission("tasks.create")),
    db: Session = Depends(get_db),
):
    """Creates a self-assigned operational task for the authenticated user."""
    full_data = TaskCreate(
        title=data.title,
        description=data.description,
        vertical_id=data.vertical_id,
        task_type=data.task_type,
        priority=data.priority,
        deadline=data.deadline,
        blockers=data.blockers,
        remarks=data.remarks,
        evidence_link=data.evidence_link,
        is_self_task=True,
        assigned_to_id=current_user.id,
    )
    service = TaskService(db)
    task = service.create_task(full_data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single master task details within authorized scope."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to access this task")

    return _format_task_response(task)


@tasks_router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates master task attributes."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to update this task")

    task = service.update_task(task_id, data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/transition", response_model=TaskResponse)
async def transition_task_status(
    task_id: uuid.UUID,
    data: TaskTransitionRequest,
    current_user: User = Depends(require_permission("tasks.transition")),
    db: Session = Depends(get_db),
):
    """Transitions task status with completion & health validation."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to transition this task")

    task = service.transition_status(task_id, data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: uuid.UUID,
    data: TaskAssignRequest,
    current_user: User = Depends(require_permission("tasks.assign")),
    db: Session = Depends(get_db),
):
    """Assigns task to a user within the task's vertical division."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to assign this task")

    task = service.assign_task(task_id, data.assigned_to_id, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/reassign", response_model=TaskResponse)
async def reassign_task(
    task_id: uuid.UUID,
    data: TaskReassignRequest,
    current_user: User = Depends(require_permission("tasks.assign")),
    db: Session = Depends(get_db),
):
    """Reassigns task to a user within the task's vertical division."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to reassign this task")

    task = service.reassign_task(task_id, data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/escalate", response_model=TaskResponse)
async def escalate_task(
    task_id: uuid.UUID,
    data: TaskEscalateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Escalates a task with operational justification."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to escalate this task")

    task = service.escalate_task(task_id, data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/resolve-escalation", response_model=TaskResponse)
async def resolve_task_escalation(
    task_id: uuid.UUID,
    data: TaskResolveEscalationRequest,
    current_user: User = Depends(require_permission("tasks.update")),
    db: Session = Depends(get_db),
):
    """Resolves an active task escalation."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to resolve escalation on this task")

    task = service.resolve_escalation(task_id, data, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/block", response_model=TaskResponse)
async def block_task(
    task_id: uuid.UUID,
    data: TaskBlockRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marks a task as blocked with blocker description."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to block this task")

    task = service.block_task(task_id, data.blocker_description, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.post("/tasks/{task_id}/unblock", response_model=TaskResponse)
async def unblock_task(
    task_id: uuid.UUID,
    data: TaskUnblockRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unblocks a task."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to unblock this task")

    task = service.unblock_task(task_id, data.resolution, actor_id=current_user.id)
    db.commit()
    return _format_task_response(service.get_task_by_id(task.id))


@tasks_router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists comments for a task."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to access comments on this task")

    comments = service.list_comments(task_id)
    return [
        TaskCommentResponse(
            id=c.id,
            task_id=c.task_id,
            author_id=c.author_id,
            author_username=c.author.username if c.author else None,
            author_name=c.author.full_name if c.author else None,
            content=c.content,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in comments
    ]


@tasks_router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_task_comment(
    task_id: uuid.UUID,
    data: TaskCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Adds a comment to a task."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to comment on this task")

    comment = service.add_comment(task_id, author_id=current_user.id, content=data.content)
    db.commit()
    return TaskCommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        author_username=current_user.username,
        author_name=current_user.full_name,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@tasks_router.get("/tasks/{task_id}/history", response_model=list[TaskHistoryResponse])
async def list_task_history(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists immutable history for a task."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    service = TaskService(db)
    task = service.get_task_by_id(task_id)
    auth_service = AuthorityService(db)
    if not auth_service.can_access_object(current_user, "task", task):
        raise ForbiddenException("You do not have authorization to view history for this task")

    entries = service.list_history(task_id)
    return [
        TaskHistoryResponse(
            id=h.id,
            task_id=h.task_id,
            actor_id=h.actor_id,
            actor_username=h.actor.username if h.actor else None,
            action=h.action,
            previous_value=h.previous_value,
            new_value=h.new_value,
            timestamp=h.timestamp,
            correlation_id=h.correlation_id,
        )
        for h in entries
    ]

