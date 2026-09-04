"""
Announcements API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.communication import AnnouncementStatus
from app.models.user import User
from app.schemas.communication import (
    AnnouncementCreate,
    AnnouncementListResponse,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.services.announcement_service import AnnouncementService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

router = APIRouter(prefix="/announcements", tags=["Announcements"])


def _format_announcement_response(a) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=a.id,
        title=a.title,
        content=a.content,
        category=a.category,
        priority=a.priority,
        scope=a.scope,
        vertical_id=a.vertical_id,
        vertical_name=a.vertical.name if a.vertical else None,
        event_id=a.event_id,
        event_name=a.event.name if hasattr(a, "event") and a.event else None,
        target_user_id=a.target_user_id,
        target_username=a.target_user.username if a.target_user else None,
        author_id=a.author_id,
        author_username=a.author.username if a.author else None,
        status=a.status,
        published_at=a.published_at,
        expires_at=a.expires_at,
        archived_at=a.archived_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=AnnouncementListResponse, dependencies=[Depends(require_permissions(["announcements.read"]))])
def list_announcements(
    status: Optional[AnnouncementStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    rbac = RbacService(db)
    org = OrganizationService(db)

    user_roles = {r.name for r in rbac.get_user_roles(current_user.id)}
    is_admin = "ADMIN" in user_roles or "SPORTS_CORE" in user_roles
    user_verticals = [v.id for v, _ in org.get_user_verticals(current_user.id)]

    items, total = service.list_announcements(
        current_user=current_user,
        user_vertical_ids=user_verticals,
        status=status,
        is_admin=is_admin,
        limit=limit,
        offset=offset,
    )
    return AnnouncementListResponse(total=total, items=[_format_announcement_response(a) for a in items])


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["announcements.create"]))])
def create_announcement(
    data: AnnouncementCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = service.create_announcement(data, author_id=current_user.id)
    db.commit()
    return _format_announcement_response(service.get_announcement_by_id(announcement.id))


@router.get("/{announcement_id}", response_model=AnnouncementResponse, dependencies=[Depends(require_permissions(["announcements.read"]))])
def get_announcement(
    announcement_id: UUID,
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    return _format_announcement_response(service.get_announcement_by_id(announcement_id))


@router.patch("/{announcement_id}", response_model=AnnouncementResponse, dependencies=[Depends(require_permissions(["announcements.update"]))])
def update_announcement(
    announcement_id: UUID,
    data: AnnouncementUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = service.update_announcement(announcement_id, data, actor_id=current_user.id)
    db.commit()
    return _format_announcement_response(service.get_announcement_by_id(announcement.id))


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse, dependencies=[Depends(require_permissions(["announcements.publish"]))])
def publish_announcement(
    announcement_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = service.publish_announcement(announcement_id, actor_id=current_user.id)
    db.commit()
    return _format_announcement_response(service.get_announcement_by_id(announcement.id))


@router.post("/{announcement_id}/archive", response_model=AnnouncementResponse, dependencies=[Depends(require_permissions(["announcements.archive"]))])
def archive_announcement(
    announcement_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = service.archive_announcement(announcement_id, actor_id=current_user.id)
    db.commit()
    return _format_announcement_response(service.get_announcement_by_id(announcement.id))
