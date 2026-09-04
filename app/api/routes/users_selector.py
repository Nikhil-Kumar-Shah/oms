"""
Users Selector API Route (Phase 10E)
Standardizes /api/v1/users/selector endpoint for universal selector queries.
Proxies to authoritative selector logic with member counts and group hierarchies.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.organization import (
    SelectorResponse,
    AudienceResolveRequest,
    AudienceResolveResponse,
)
from app.api.routes.organization import get_selector_options
from app.services.audience_service import AudienceService

router = APIRouter(prefix="/users", tags=["Users Selector"])


@router.get("/selector", response_model=SelectorResponse)
def get_users_selector(
    selection_type: str = Query(default="USER", description="Selection mode: USER, MULTI_USER, VERTICAL, ROLE, ROLE_VERTICAL, ALL_USERS, EVENT_TEAM, GROUP"),
    search: Optional[str] = Query(default=None, description="Search keyword (name, username, email, ID)"),
    role_id: Optional[str] = Query(default=None, alias="role_filter", description="Filter by canonical role"),
    vertical_id: Optional[UUID] = Query(default=None, description="Filter by vertical division ID"),
    event_id: Optional[UUID] = Query(default=None, description="Filter by event ID"),
    usage: str = Query(default="general", description="Usage context: assignment, audience, or general"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=100, ge=1, le=500, alias="limit", description="Page size"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SelectorResponse:
    """
    Universal Selector API endpoint returning structured users, groups with member counts,
    and individual entity items. Enforces server-side authorization.
    """
    offset = (page - 1) * page_size
    return get_selector_options(
        selection_type=selection_type,
        search=search,
        role_filter=role_id,
        vertical_id=vertical_id,
        event_id=event_id,
        usage=usage,
        limit=page_size,
        offset=offset,
        current_user=current_user,
        db=db,
    )


@router.post("/resolve-audience", response_model=AudienceResolveResponse)
def resolve_audience(
    request: AudienceResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceResolveResponse:
    """
    Universal Audience Resolution Endpoint. Resolves:
    - Entire organization (all_users)
    - Verticals (A OR B)
    - Roles (Role A OR Role B)
    - Combinations: (Verticals) AND (Roles)
    - Explicit individual user accounts
    Strictly deduplicates results into valid user IDs and validates caller authorization.
    """
    service = AudienceService(db)
    return service.resolve_audience(request, actor=current_user)


@router.get("/{user_id}")
def get_user_by_id_scoped(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Direct user lookup by UUID (/api/v1/users/{user_id}).
    Enforces strict vertical scoping for non-executive roles.
    Returns 403 Forbidden if the requester and target do not share an authorized vertical.
    """
    from app.core.exceptions import ForbiddenException, EntityNotFoundException
    from app.services.authority_service import AuthorityService
    from app.services.user_service import UserService
    from app.services.rbac_service import RbacService
    from app.services.organization_service import OrganizationService
    from app.schemas.user import UserResponse, UserRoleSummary, UserVerticalSummary

    authority_service = AuthorityService(db)
    user_service = UserService(db)

    target_user = user_service.get_user_by_id(user_id)
    if not target_user:
        raise EntityNotFoundException("User", str(user_id))

    if not authority_service.is_executive_or_admin(current_user.id):
        if not authority_service.can_access_object(current_user, "user", target_user):
            raise ForbiddenException("You do not have access to view this user profile")

    rbac_service = RbacService(db)
    org_service = OrganizationService(db)
    roles = [ur.role for ur in target_user.user_roles if ur.role] if hasattr(target_user, "user_roles") and target_user.user_roles else rbac_service.get_user_roles(target_user.id)
    verts = [(uv.vertical, uv.is_primary) for uv in target_user.user_verticals if uv.vertical] if hasattr(target_user, "user_verticals") and target_user.user_verticals else org_service.get_user_verticals(target_user.id)

    return UserResponse(
        id=target_user.id,
        username=target_user.username,
        full_name=target_user.full_name,
        email=target_user.email,
        account_status=target_user.account_status,
        roles=[UserRoleSummary(id=r.id, name=r.name) for r in roles],
        verticals=[UserVerticalSummary(id=v.id, name=v.name, is_primary=p) for v, p in verts],
        last_login_at=target_user.last_login_at,
        disabled_at=target_user.disabled_at,
        created_at=target_user.created_at,
        updated_at=target_user.updated_at,
    )

