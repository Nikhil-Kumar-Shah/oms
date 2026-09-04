"""
FAQ & Operational Knowledge Base API Endpoints
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.faq import FAQStatus
from app.models.user import User
from app.schemas.faq import FAQCreate, FAQListResponse, FAQResponse, FAQUpdate
from app.services.faq_service import FAQService

router = APIRouter(prefix="/faqs", tags=["Help & FAQs"])


def _format_faq_response(f) -> FAQResponse:
    return FAQResponse(
        id=f.id,
        question=f.question,
        answer=f.answer,
        category=f.category,
        display_order=f.display_order,
        status=f.status,
        target_audience=f.target_audience,
        related_route=f.related_route,
        route_label=f.route_label,
        created_by_id=f.created_by_id,
        created_by_username=f.created_by.username if f.created_by else None,
        updated_by_id=f.updated_by_id,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


@router.get("", response_model=FAQListResponse, status_code=status.HTTP_200_OK)
def list_faqs(
    category: Optional[str] = Query(None),
    status: Optional[FAQStatus] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FAQService(db)
    faqs, total = service.list_faqs(
        category=category,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    items = [_format_faq_response(f) for f in faqs]
    return FAQListResponse(total=total, items=items)


@router.post("", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(
    data: FAQCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_manage_faqs(current_user.id):
        raise ForbiddenException("Only executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN) can create, edit, or delete FAQs")

    service = FAQService(db)
    faq = service.create_faq(data, actor_id=current_user.id)
    db.commit()
    return _format_faq_response(service.get_faq_by_id(faq.id))


@router.get("/{faq_id}", response_model=FAQResponse, status_code=status.HTTP_200_OK)
def get_faq(
    faq_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FAQService(db)
    return _format_faq_response(service.get_faq_by_id(faq_id))


@router.patch("/{faq_id}", response_model=FAQResponse, status_code=status.HTTP_200_OK)
def update_faq(
    faq_id: UUID,
    data: FAQUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_manage_faqs(current_user.id):
        raise ForbiddenException("Only executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN) can create, edit, or delete FAQs")

    service = FAQService(db)
    faq = service.update_faq(faq_id, data, actor_id=current_user.id)
    db.commit()
    return _format_faq_response(service.get_faq_by_id(faq.id))


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq(
    faq_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.can_manage_faqs(current_user.id):
        raise ForbiddenException("Only executive leadership (SPORTS_CORE, DEPUTY_CORE, ADMIN) can create, edit, or delete FAQs")

    service = FAQService(db)
    service.delete_faq(faq_id, actor_id=current_user.id)
    db.commit()
    return None
