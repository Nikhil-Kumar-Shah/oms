"""
Cross-Vertical Requirements API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.core.exceptions import ForbiddenException
from app.models.requirement import RequirementPriority, RequirementStatus
from app.models.user import User
from app.schemas.requirement import (
    RequirementAssignRequest,
    RequirementCreate,
    RequirementEscalateRequest,
    RequirementForwardRequest,
    RequirementListResponse,
    RequirementMessageCreate,
    RequirementMessageResponse,
    RequirementResolveEscalationRequest,
    RequirementResponse,
    RequirementTransitionRequest,
    RequirementUpdate,
)
from app.services.authority_service import AuthorityService
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/requirements", tags=["Requirements"])


def _format_requirement_response(r) -> RequirementResponse:
    return RequirementResponse(
        id=r.id,
        title=r.title,
        description=r.description,
        event_id=r.event_id,
        event_name=r.event.name if getattr(r, "event", None) else None,
        responsible_poc_id=r.responsible_poc_id,
        responsible_poc_username=r.responsible_poc.username if getattr(r, "responsible_poc", None) else None,
        responsible_poc_full_name=r.responsible_poc.full_name if getattr(r, "responsible_poc", None) else None,
        requesting_vertical_id=r.requesting_vertical_id,
        requesting_vertical_name=r.requesting_vertical.name if getattr(r, "requesting_vertical", None) else None,
        target_vertical_id=r.target_vertical_id,
        target_vertical_name=r.target_vertical.name if getattr(r, "target_vertical", None) else None,
        requester_id=r.requester_id,
        requester_username=r.requester.username if getattr(r, "requester", None) else None,
        requester_full_name=r.requester.full_name if getattr(r, "requester", None) else None,
        assignee_id=r.assignee_id,
        assignee_username=r.assignee.username if getattr(r, "assignee", None) else None,
        assignee_full_name=r.assignee.full_name if getattr(r, "assignee", None) else None,
        priority=r.priority,
        status=r.status,
        deadline=r.deadline,
        remarks=r.remarks,
        reference_link=r.reference_link,
        forward_history=r.forward_history or [],
        is_escalated=r.is_escalated or False,
        escalated_to_id=r.escalated_to_id,
        escalated_to_username=r.escalated_to.username if getattr(r, "escalated_to", None) else None,
        escalated_to_full_name=r.escalated_to.full_name if getattr(r, "escalated_to", None) else None,
        escalated_by_id=r.escalated_by_id,
        escalated_by_username=r.escalated_by.username if getattr(r, "escalated_by", None) else None,
        escalated_by_full_name=r.escalated_by.full_name if getattr(r, "escalated_by", None) else None,
        escalated_at=r.escalated_at,
        escalation_reason=r.escalation_reason,
        escalation_status=r.escalation_status,
        escalation_resolved_at=r.escalation_resolved_at,
        escalation_resolved_by_id=r.escalation_resolved_by_id,
        escalation_resolution_notes=r.escalation_resolution_notes,
        created_at=r.created_at,
        updated_at=r.updated_at,
        messages_count=len(r.messages) if getattr(r, "messages", None) else 0,
    )


def _format_message_response(m) -> RequirementMessageResponse:
    return RequirementMessageResponse(
        id=m.id,
        requirement_id=m.requirement_id,
        author_id=m.author_id,
        author_username=m.author.username if m.author else None,
        author_full_name=m.author.full_name if m.author else None,
        content=m.content,
        created_at=m.created_at,
    )


@router.get("", response_model=RequirementListResponse, dependencies=[Depends(require_permissions(["requirements.read"]))])
def list_requirements(
    requesting_vertical_id: Optional[UUID] = Query(None),
    target_vertical_id: Optional[UUID] = Query(None),
    event_id: Optional[UUID] = Query(None),
    status: Optional[RequirementStatus] = Query(None),
    priority: Optional[RequirementPriority] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = RequirementService(db)
    reqs, total = service.list_requirements(
        requesting_vertical_id=requesting_vertical_id,
        target_vertical_id=target_vertical_id,
        event_id=event_id,
        status=status,
        priority=priority,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    items = [_format_requirement_response(r) for r in reqs]
    return RequirementListResponse(total=total, items=items)


@router.post("", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["requirements.create"]))])
def create_requirement(
    data: RequirementCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    # Requirements are especially for Event Teams only (or Admin in system testing/override)
    if not (auth_service.is_event_team(current_user.id) or auth_service.is_admin(current_user.id)):
        raise ForbiddenException("Only Event Team accounts are authorized to create requirements")

    service = RequirementService(db)
    req = service.create_requirement(data, requester_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.get("/{requirement_id}", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.read"]))])
def get_requirement(
    requirement_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = RequirementService(db)
    return _format_requirement_response(service.get_requirement_by_id(requirement_id, current_user=current_user))


@router.patch("/{requirement_id}", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.create"]))])
def update_requirement(
    requirement_id: UUID,
    data: RequirementUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    # Event Team cannot modify once created; only add messages
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot modify requirement configuration")

    service = RequirementService(db)
    req = service.update_requirement(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.post("/{requirement_id}/assign", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.assign"]))])
def assign_requirement(
    requirement_id: UUID,
    data: RequirementAssignRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot assign requirements")

    service = RequirementService(db)
    req = service.assign_requirement(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.post("/{requirement_id}/forward", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.update"]))])
def forward_requirement(
    requirement_id: UUID,
    data: RequirementForwardRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot forward requirements")

    service = RequirementService(db)
    req = service.forward_requirement(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.post("/{requirement_id}/transition", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.transition"]))])
def transition_requirement(
    requirement_id: UUID,
    data: RequirementTransitionRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot change requirement status")

    service = RequirementService(db)
    req = service.transition_status(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.post("/{requirement_id}/escalate", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.update"]))])
def escalate_requirement(
    requirement_id: UUID,
    data: RequirementEscalateRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot escalate requirements")

    service = RequirementService(db)
    req = service.escalate_requirement(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.post("/{requirement_id}/resolve-escalation", response_model=RequirementResponse, dependencies=[Depends(require_permissions(["requirements.update"]))])
def resolve_requirement_escalation(
    requirement_id: UUID,
    data: RequirementResolveEscalationRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthorityService(db)
    if auth_service.is_event_team(current_user.id):
        raise ForbiddenException("Event Team cannot resolve requirement escalations")

    service = RequirementService(db)
    req = service.resolve_requirement_escalation(requirement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_requirement_response(service.get_requirement_by_id(req.id, current_user=current_user))


@router.get("/{requirement_id}/messages", response_model=List[RequirementMessageResponse], dependencies=[Depends(require_permissions(["requirements.read"]))])
def list_messages(
    requirement_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = RequirementService(db)
    # verify user can view requirement
    service.get_requirement_by_id(requirement_id, current_user=current_user)
    messages = service.list_messages(requirement_id)
    return [_format_message_response(m) for m in messages]


@router.post("/{requirement_id}/messages", response_model=RequirementMessageResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["requirements.message"]))])
def add_message(
    requirement_id: UUID,
    data: RequirementMessageCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = RequirementService(db)
    # verify user can view/comment on requirement
    service.get_requirement_by_id(requirement_id, current_user=current_user)
    msg = service.add_message(requirement_id, data, author_id=current_user.id)
    db.commit()
    return _format_message_response(msg)
