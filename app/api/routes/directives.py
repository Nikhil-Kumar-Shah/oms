"""
Directives & Compliance API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.communication import DirectiveStatus
from app.models.user import User
from app.schemas.communication import (
    DirectiveAcknowledgeRequest,
    DirectiveAcknowledgementResponse,
    DirectiveCreate,
    DirectiveListResponse,
    DirectiveResponse,
    DirectiveUpdate,
)
from app.services.directive_service import DirectiveService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

router = APIRouter(prefix="/directives", tags=["Directives & Compliance"])


def _format_ack_response(ack) -> DirectiveAcknowledgementResponse:
    return DirectiveAcknowledgementResponse(
        id=ack.id,
        directive_id=ack.directive_id,
        user_id=ack.user_id,
        username=ack.user.username if ack.user else None,
        full_name=ack.user.full_name if ack.user else None,
        status=ack.status,
        acknowledged_at=ack.acknowledged_at,
        notes=ack.notes,
        created_at=ack.created_at,
    )


def _format_directive_response(d) -> DirectiveResponse:
    acks = [_format_ack_response(ack) for ack in d.acknowledgements] if d.acknowledgements else []
    acked_cnt = sum(1 for ack in acks if ack.status.value == "ACKNOWLEDGED")
    return DirectiveResponse(
        id=d.id,
        title=d.title,
        instruction=d.instruction,
        issued_by_id=d.issued_by_id,
        issued_by_username=d.issued_by.username if d.issued_by else None,
        scope=d.scope,
        vertical_id=d.vertical_id,
        vertical_name=d.vertical.name if d.vertical else None,
        target_user_id=d.target_user_id,
        target_username=d.target_user.username if d.target_user else None,
        priority=d.priority,
        effective_date=d.effective_date,
        deadline=d.deadline,
        status=d.status,
        requires_acknowledgement=d.requires_acknowledgement,
        created_at=d.created_at,
        updated_at=d.updated_at,
        acknowledgements=acks,
        total_acknowledgements=len(acks),
        acknowledged_count=acked_cnt,
    )


@router.get("", response_model=DirectiveListResponse, dependencies=[Depends(require_permissions(["directives.read"]))])
def list_directives(
    status: Optional[DirectiveStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    rbac = RbacService(db)
    org = OrganizationService(db)

    user_roles = {r.name for r in rbac.get_user_roles(current_user.id)}
    is_admin = "ADMIN" in user_roles or "SPORTS_CORE" in user_roles
    user_verticals = [v.id for v, _ in org.get_user_verticals(current_user.id)]

    items, total = service.list_directives(
        current_user=current_user,
        user_vertical_ids=user_verticals,
        status=status,
        is_admin=is_admin,
        limit=limit,
        offset=offset,
    )
    return DirectiveListResponse(total=total, items=[_format_directive_response(d) for d in items])


@router.post("", response_model=DirectiveResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["directives.create"]))])
def create_directive(
    data: DirectiveCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    directive = service.create_directive(data, issued_by_id=current_user.id)
    db.commit()
    return _format_directive_response(service.get_directive_by_id(directive.id))


@router.get("/{directive_id}", response_model=DirectiveResponse, dependencies=[Depends(require_permissions(["directives.read"]))])
def get_directive(
    directive_id: UUID,
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    return _format_directive_response(service.get_directive_by_id(directive_id))


@router.patch("/{directive_id}", response_model=DirectiveResponse, dependencies=[Depends(require_permissions(["directives.update"]))])
def update_directive(
    directive_id: UUID,
    data: DirectiveUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    directive = service.update_directive(directive_id, data, actor_id=current_user.id)
    db.commit()
    return _format_directive_response(service.get_directive_by_id(directive.id))


@router.post("/{directive_id}/issue", response_model=DirectiveResponse, dependencies=[Depends(require_permissions(["directives.issue"]))])
def issue_directive(
    directive_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    directive = service.issue_directive(directive_id, actor_id=current_user.id)
    db.commit()
    return _format_directive_response(service.get_directive_by_id(directive.id))


@router.post("/{directive_id}/acknowledge", response_model=DirectiveAcknowledgementResponse, dependencies=[Depends(require_permissions(["directives.acknowledge"]))])
def acknowledge_directive(
    directive_id: UUID,
    data: DirectiveAcknowledgeRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = DirectiveService(db)
    ack = service.acknowledge_directive(directive_id, user_id=current_user.id, data=data)
    db.commit()
    return _format_ack_response(ack)
