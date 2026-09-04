"""
Issue & Escalation Register API Endpoints
Paradox Sports OMS - Phase 3 Core Operational System
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.models.issue import IssueSensitivity, IssueStatus
from app.models.user import User
from app.schemas.issue import (
    IssueCommentCreate,
    IssueCommentResponse,
    IssueCreate,
    IssueEscalateRequest,
    IssueHistoryResponse,
    IssueListResponse,
    IssueResponse,
    IssueTransitionRequest,
    IssueUpdate,
)
from app.services.issue_service import IssueService

issues_router = APIRouter(prefix="/issues", tags=["Issue & Escalation Register"])


def _format_issue_response(issue) -> IssueResponse:
    """Helper to convert issue model to response schema."""
    assignees_list = []
    assignee_ids = []

    if getattr(issue, "issue_assignees", None):
        for ia in issue.issue_assignees:
            assignee_ids.append(ia.user_id)
            if ia.user:
                assignees_list.append({
                    "id": ia.user.id,
                    "username": ia.user.username,
                    "full_name": ia.user.full_name,
                })
            else:
                assignees_list.append({
                    "id": ia.user_id,
                    "username": str(ia.user_id),
                    "full_name": None,
                })
    elif issue.assigned_to_id:
        assignee_ids.append(issue.assigned_to_id)
        if issue.assigned_to:
            assignees_list.append({
                "id": issue.assigned_to.id,
                "username": issue.assigned_to.username,
                "full_name": issue.assigned_to.full_name,
            })

    return IssueResponse(
        id=issue.id,
        date_raised=issue.date_raised,
        vertical_id=issue.vertical_id,
        vertical_name=issue.vertical.name if issue.vertical else None,
        event_reference=issue.event_reference,
        title=issue.title,
        description=issue.description,
        raised_by_id=issue.raised_by_id,
        raised_by_username=issue.raised_by.username if issue.raised_by else None,
        assigned_to_id=issue.assigned_to_id,
        assigned_to_username=issue.assigned_to.username if issue.assigned_to else None,
        assignee_ids=assignee_ids,
        assignees=assignees_list,
        sensitivity=issue.sensitivity,
        status=issue.status,
        action_required=issue.action_required,
        deadline=issue.deadline,
        escalation_target=issue.escalation_target,
        escalation_action=issue.escalation_action,
        resolution=issue.resolution,
        resolution_date=issue.resolution_date,
        evidence_link=issue.evidence_link,
        remarks=issue.remarks,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@issues_router.get("", response_model=IssueListResponse)
async def list_issues(
    vertical_id: Optional[uuid.UUID] = Query(None),
    status: Optional[IssueStatus] = Query(None),
    sensitivity: Optional[IssueSensitivity] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists issues in the register with sensitivity-based authorization."""
    service = IssueService(db)
    items, total = service.list_issues(
        current_user=current_user,
        vertical_id=vertical_id,
        status=status,
        sensitivity=sensitivity,
        skip=skip,
        limit=limit,
    )
    return IssueListResponse(total=total, items=[_format_issue_response(i) for i in items])


@issues_router.post("", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def create_issue(
    data: IssueCreate,
    current_user: User = Depends(require_permission("issues.create")),
    db: Session = Depends(get_db),
):
    """Creates a new issue in the register."""
    service = IssueService(db)
    issue = service.create_issue(data, actor_id=current_user.id)
    db.commit()
    return _format_issue_response(service.get_issue_by_id(issue.id, current_user=current_user))


@issues_router.get("/{issue_id}", response_model=IssueResponse)
async def get_issue(
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves issue details with sensitivity authorization."""
    service = IssueService(db)
    issue = service.get_issue_by_id(issue_id, current_user=current_user)
    return _format_issue_response(issue)


@issues_router.patch("/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: uuid.UUID,
    data: IssueUpdate,
    current_user: User = Depends(require_permission("issues.update")),
    db: Session = Depends(get_db),
):
    """Updates issue details."""
    service = IssueService(db)
    issue = service.update_issue(issue_id, data, actor_id=current_user.id)
    db.commit()
    return _format_issue_response(service.get_issue_by_id(issue.id, current_user=current_user))


@issues_router.post("/{issue_id}/transition", response_model=IssueResponse)
async def transition_issue_status(
    issue_id: uuid.UUID,
    data: IssueTransitionRequest,
    current_user: User = Depends(require_permission("issues.update")),
    db: Session = Depends(get_db),
):
    """Transitions issue status with resolution."""
    service = IssueService(db)
    issue = service.transition_status(issue_id, data, actor_id=current_user.id)
    db.commit()
    return _format_issue_response(service.get_issue_by_id(issue.id, current_user=current_user))


@issues_router.post("/{issue_id}/escalate", response_model=IssueResponse)
async def escalate_issue(
    issue_id: uuid.UUID,
    data: IssueEscalateRequest,
    current_user: User = Depends(require_permission("issues.escalate")),
    db: Session = Depends(get_db),
):
    """Escalates issue to designated leadership."""
    service = IssueService(db)
    issue = service.escalate_issue(issue_id, data, actor_id=current_user.id)
    db.commit()
    return _format_issue_response(service.get_issue_by_id(issue.id, current_user=current_user))


@issues_router.get("/{issue_id}/history", response_model=list[IssueHistoryResponse])
async def list_issue_history(
    issue_id: uuid.UUID,
    current_user: User = Depends(require_permission("issues.read")),
    db: Session = Depends(get_db),
):
    """Lists history entries for an issue."""
    service = IssueService(db)
    entries = service.list_history(issue_id)
    return [
        IssueHistoryResponse(
            id=h.id,
            issue_id=h.issue_id,
            actor_id=h.actor_id,
            actor_username=h.actor.username if h.actor else None,
            action=h.action,
            details=h.details,
            timestamp=h.timestamp,
            correlation_id=h.correlation_id,
        )
        for h in entries
    ]


@issues_router.get("/{issue_id}/comments", response_model=list[IssueCommentResponse])
async def list_issue_comments(
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists comments for an issue."""
    service = IssueService(db)
    # Ensures the user has access to this issue (vertical scope + sensitivity check)
    service.get_issue_by_id(issue_id, current_user=current_user)

    comments = service.list_comments(issue_id)
    return [
        IssueCommentResponse(
            id=c.id,
            issue_id=c.issue_id,
            author_id=c.author_id,
            author_username=c.author.username if c.author else None,
            author_name=c.author.full_name if c.author else None,
            content=c.content,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in comments
    ]


@issues_router.post("/{issue_id}/comments", response_model=IssueCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_issue_comment(
    issue_id: uuid.UUID,
    data: IssueCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Adds a comment to an issue."""
    service = IssueService(db)
    # Ensures the user has access to this issue (vertical scope + sensitivity check)
    service.get_issue_by_id(issue_id, current_user=current_user)

    comment = service.add_comment(issue_id, author_id=current_user.id, content=data.content)
    db.commit()
    return IssueCommentResponse(
        id=comment.id,
        issue_id=comment.issue_id,
        author_id=comment.author_id,
        author_username=current_user.username,
        author_name=current_user.full_name,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )
