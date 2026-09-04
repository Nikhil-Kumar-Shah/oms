"""
Communication Tracker API Endpoints
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.communication import CommunicationLogStatus, CommunicationType
from app.models.user import User
from app.schemas.communication import (
    CommunicationLogCreate,
    CommunicationLogListResponse,
    CommunicationLogResponse,
    CommunicationLogUpdate,
)
from app.services.communication_service import CommunicationLogService

router = APIRouter(prefix="/communications", tags=["Communication Tracker"])


def _format_comm_response(c) -> CommunicationLogResponse:
    return CommunicationLogResponse(
        id=c.id,
        date_time=c.date_time,
        communication_type=c.communication_type,
        subject=c.subject,
        sender_info=c.sender_info,
        recipient_info=c.recipient_info,
        vertical_id=c.vertical_id,
        vertical_name=c.vertical.name if c.vertical else None,
        event_id=c.event_id,
        event_name=c.event.name if hasattr(c, "event") and c.event else None,
        related_resource_type=c.related_resource_type,
        related_resource_id=c.related_resource_id,
        reference_link=c.reference_link,
        remarks=c.remarks,
        created_by_id=c.created_by_id,
        created_by_username=c.created_by.username if c.created_by else None,
        status=c.status,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=CommunicationLogListResponse, dependencies=[Depends(require_permissions(["communications.read"]))])
def list_communication_logs(
    vertical_id: Optional[UUID] = Query(None),
    event_id: Optional[UUID] = Query(None),
    communication_type: Optional[CommunicationType] = Query(None),
    status: Optional[CommunicationLogStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_access_official_communications(current_user.id):
        raise ForbiddenException("Access to Official Communication Logs is restricted to executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN)")

    service = CommunicationLogService(db)
    items, total = service.list_logs(
        vertical_id=vertical_id,
        event_id=event_id,
        communication_type=communication_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return CommunicationLogListResponse(total=total, items=[_format_comm_response(c) for c in items])


@router.post("", response_model=CommunicationLogResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["communications.create"]))])
def create_communication_log(
    data: CommunicationLogCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_access_official_communications(current_user.id):
        raise ForbiddenException("Access to Official Communication Logs is restricted to executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN)")

    service = CommunicationLogService(db)
    log = service.create_log(data, created_by_id=current_user.id)
    db.commit()
    return _format_comm_response(service.get_log_by_id(log.id))


@router.get("/{log_id}", response_model=CommunicationLogResponse, dependencies=[Depends(require_permissions(["communications.read"]))])
def get_communication_log(
    log_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_access_official_communications(current_user.id):
        raise ForbiddenException("Access to Official Communication Logs is restricted to executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN)")

    service = CommunicationLogService(db)
    return _format_comm_response(service.get_log_by_id(log_id))


@router.patch("/{log_id}", response_model=CommunicationLogResponse, dependencies=[Depends(require_permissions(["communications.update"]))])
def update_communication_log(
    log_id: UUID,
    data: CommunicationLogUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_access_official_communications(current_user.id):
        raise ForbiddenException("Access to Official Communication Logs is restricted to executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN)")

    service = CommunicationLogService(db)
    log = service.update_log(log_id, data, actor_id=current_user.id)
    db.commit()
    return _format_comm_response(service.get_log_by_id(log.id))
