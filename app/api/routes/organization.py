"""
Organization & Vertical API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.organization import VerticalStatus
from app.models.user import AccountStatus, User
from app.schemas.organization import (
    AudienceResolveRequest,
    AudienceResolveResponse,
    OrganizationResponse,
    SelectorItem,
    SelectorResponse,
    VerticalListResponse,
    VerticalResponse,
)
from app.schemas.user import UserListResponse
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organization", tags=["Organization"])


@router.get(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Organization Details",
    description="Returns organization info and associated active vertical divisions.",
)
def get_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    org_service = OrganizationService(db)
    org = org_service.get_organization()
    verticals = org_service.list_verticals(org.id)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        code=org.code,
        description=org.description,
        created_at=org.created_at,
        updated_at=org.updated_at,
        verticals=[VerticalResponse.model_validate(v) for v in verticals],
    )


@router.get(
    "/verticals",
    response_model=VerticalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Verticals",
    description="Returns list of all active organizational vertical divisions.",
)
def list_verticals(
    status_filter: Optional[VerticalStatus] = Query(default=VerticalStatus.ACTIVE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalListResponse:
    org_service = OrganizationService(db)
    verticals = org_service.list_verticals(status_filter=status_filter)

    return VerticalListResponse(
        total=len(verticals),
        items=[VerticalResponse.model_validate(v) for v in verticals],
    )


@router.get(
    "/verticals/{vertical_id}",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Vertical Details",
    description="Returns vertical division by UUID.",
)
def get_vertical(
    vertical_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    org_service = OrganizationService(db)
    vertical = org_service.get_vertical(vertical_id)
    return VerticalResponse.model_validate(vertical)


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Organization Members",
    description="Searches active organizational members for assignment and operational collaboration.",
)
def search_organization_users(
    search: Optional[str] = Query(None, description="Search term for username, full name, or email"),
    vertical_id: Optional[UUID] = Query(None, description="Filter by vertical division"),
    role_filter: Optional[str] = Query(None, description="Filter by role name"),
    status_filter: Optional[AccountStatus] = Query(None, description="Filter by account status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserListResponse:
    from app.services.user_service import UserService
    from app.services.rbac_service import RbacService
    from app.services.authority_service import AuthorityService
    from app.schemas.user import UserResponse, UserRoleSummary, UserVerticalSummary

    user_service = UserService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)
    authority_service = AuthorityService(db)

    effective_status = status_filter if status_filter is not None else AccountStatus.ACTIVE

    scoped_vertical_id = vertical_id
    scoped_vertical_ids = None
    allowed_user_ids = None

    if not authority_service.is_executive_or_admin(current_user.id):
        user_roles = authority_service.get_user_role_names(current_user.id)
        if "EVENT_TEAM" in user_roles:
            event_ids = authority_service.get_user_event_ids(current_user.id)
            from app.models.event import EventMember, EventTeamProfile
            member_uids = db.scalars(
                select(EventMember.user_id).where(EventMember.event_id.in_(event_ids))
            ).all() if event_ids else []
            team_uids = db.scalars(
                select(EventTeamProfile.user_id).where(EventTeamProfile.event_id.in_(event_ids))
            ).all() if event_ids else []
            allowed_user_ids = set(member_uids) | set(team_uids) | {current_user.id}
        else:
            # Internal roles (SUPER_COORDINATOR, COORDINATOR, VOLUNTEER):
            # When no vertical_id is explicitly requested, scoped_vertical_ids stays None
            # so list_users returns all active users across the entire platform.
            assigned_vids = authority_service.get_user_vertical_ids(current_user.id)
            if scoped_vertical_id:
                if scoped_vertical_id not in assigned_vids:
                    scoped_vertical_ids = []
                    scoped_vertical_id = None
                else:
                    scoped_vertical_ids = [scoped_vertical_id]
                    scoped_vertical_id = None
            # else: no vertical filter -> leave scoped_vertical_ids as None (all platform users)

    users = user_service.list_users(
        status_filter=effective_status,
        search=search,
        role_filter=role_filter,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
        allowed_user_ids=allowed_user_ids,
        limit=limit,
        offset=offset,
    )
    total = user_service.count_users(
        status_filter=effective_status,
        search=search,
        role_filter=role_filter,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
        allowed_user_ids=allowed_user_ids,
    )

    items = []
    for u in users:
        roles = rbac_service.get_user_roles(u.id)
        verts = org_service.get_user_verticals(u.id)
        items.append(
            UserResponse(
                id=u.id,
                username=u.username,
                full_name=u.full_name,
                email=u.email,
                account_status=u.account_status,
                roles=[UserRoleSummary(id=r.id, name=r.name) for r in roles],
                verticals=[UserVerticalSummary(id=v.id, name=v.name, is_primary=p) for v, p in verts],
                last_login_at=u.last_login_at,
                disabled_at=u.disabled_at,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
        )

    return UserListResponse(total=total, items=items)


@router.get(
    "/selector-options",
    response_model=SelectorResponse,
    status_code=status.HTTP_200_OK,
    summary="Universal Selector Options",
    description="Centralized, database-backed query endpoint for the Universal Selector supporting USER, MULTI_USER, VERTICAL, ROLE, ROLE_IN_VERTICAL, ALL_USERS, and EVENT_TEAM modes.",
)
def get_selector_options(
    selection_type: str = Query("USER", description="Selection mode: USER, MULTI_USER, VERTICAL, ROLE, ROLE_IN_VERTICAL, ALL_USERS, EVENT_TEAM"),
    search: Optional[str] = Query(None, description="Debounced search query"),
    vertical_id: Optional[UUID] = Query(None, description="Optional vertical filter"),
    role_filter: Optional[str] = Query(None, description="Optional role filter"),
    event_id: Optional[UUID] = Query(None, description="Optional event filter"),
    usage: Optional[str] = Query("general", description="Usage context: 'assignment', 'audience', 'general'"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SelectorResponse:
    from sqlalchemy import select, func
    from app.services.user_service import UserService
    from app.services.rbac_service import RbacService
    from app.services.authority_service import AuthorityService, INTERNAL_OPERATIONAL_HIERARCHY
    from app.models.organization import UserVertical
    from app.models.rbac import UserRole, Role
    from app.schemas.organization import SelectorGroupItem, SelectorUserItem

    org_service = OrganizationService(db)
    user_service = UserService(db)
    rbac_service = RbacService(db)
    authority_service = AuthorityService(db)

    mode = selection_type.upper().strip()

    # 1. VERTICAL SELECTION
    if mode == "VERTICAL":
        vert_counts_stmt = (
            select(UserVertical.vertical_id, func.count(User.id))
            .join(User, UserVertical.user_id == User.id)
            .where(User.account_status == AccountStatus.ACTIVE)
            .group_by(UserVertical.vertical_id)
        )
        vert_counts = dict(db.execute(vert_counts_stmt).all())

        if usage == "assignment" and not authority_service.is_executive_or_admin(current_user.id):
            assigned_vids = authority_service.get_user_vertical_ids(current_user.id)
            all_verts = [org_service.get_vertical(vid) for vid in assigned_vids if vid]
        else:
            all_verts = org_service.list_verticals()

        filtered_verts = []
        for v in all_verts:
            if not v:
                continue
            if v.status != VerticalStatus.ACTIVE and usage == "assignment":
                continue
            if search and search.strip():
                s_lower = search.strip().lower()
                if s_lower not in v.name.lower() and s_lower not in (v.description or "").lower():
                    continue
            filtered_verts.append(v)

        total = len(filtered_verts)
        paged_verts = filtered_verts[offset : offset + limit]
        items = [
            SelectorItem(
                id=str(v.id),
                type="VERTICAL",
                label=v.name,
                sublabel=f"Vertical Division • {vert_counts.get(v.id, 0)} members",
                badge=v.status.value,
                member_count=vert_counts.get(v.id, 0),
                metadata={"vertical_id": str(v.id), "name": v.name, "member_count": vert_counts.get(v.id, 0)},
            )
            for v in paged_verts
        ]
        groups = [
            SelectorGroupItem(
                type="vertical",
                id=str(v.id),
                name=v.name,
                member_count=vert_counts.get(v.id, 0),
                vertical_id=str(v.id),
                metadata={"status": v.status.value},
            )
            for v in paged_verts
        ]
        return SelectorResponse(selection_type=mode, total=total, items=items, groups=groups)

    # 2. ROLE SELECTION
    if mode == "ROLE":
        role_counts_stmt = (
            select(Role.name, func.count(User.id))
            .join(UserRole, Role.id == UserRole.role_id)
            .join(User, UserRole.user_id == User.id)
            .where(User.account_status == AccountStatus.ACTIVE)
            .group_by(Role.name)
        )
        role_counts = dict(db.execute(role_counts_stmt).all())

        all_roles = [
            ("SPORTS_CORE", "Sports Core", 5),
            ("DEPUTY_CORE", "Deputy Core", 4),
            ("SUPER_COORDINATOR", "Super Coordinator", 3),
            ("COORDINATOR", "Coordinator", 2),
            ("VOLUNTEER", "Volunteer", 1),
            ("EVENT_TEAM", "Event Team", 0),
        ]
        actor_level = authority_service.get_user_operational_level(current_user.id)
        is_exec_or_admin = authority_service.is_executive_or_admin(current_user.id)

        filtered_roles = []
        for r_name, r_label, r_lvl in all_roles:
            if usage == "assignment":
                if is_exec_or_admin:
                    if actor_level is not None and r_lvl >= actor_level:
                        continue
                else:
                    if actor_level is None or r_lvl >= actor_level:
                        continue
            if search and search.strip():
                s_lower = search.strip().lower()
                if s_lower not in r_name.lower() and s_lower not in r_label.lower():
                    continue
            filtered_roles.append((r_name, r_label))

        total = len(filtered_roles)
        paged_roles = filtered_roles[offset : offset + limit]
        items = [
            SelectorItem(
                id=r_name,
                type="ROLE",
                label=r_label,
                sublabel=f"Canonical Role • {role_counts.get(r_name, 0)} members",
                badge="ROLE",
                member_count=role_counts.get(r_name, 0),
                metadata={"role": r_name, "member_count": role_counts.get(r_name, 0)},
            )
            for r_name, r_label in paged_roles
        ]
        groups = [
            SelectorGroupItem(
                type="role",
                id=r_name,
                name=r_label,
                member_count=role_counts.get(r_name, 0),
                role=r_name,
            )
            for r_name, r_label in paged_roles
        ]
        return SelectorResponse(selection_type=mode, total=total, items=items, groups=groups)

    # 3. ROLE_VERTICAL SELECTION (Combinations)
    if mode in ("ROLE_VERTICAL", "GROUP"):
        role_vert_stmt = (
            select(UserVertical.vertical_id, Role.name, func.count(User.id))
            .join(User, UserVertical.user_id == User.id)
            .join(UserRole, User.id == UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(User.account_status == AccountStatus.ACTIVE)
            .group_by(UserVertical.vertical_id, Role.name)
        )
        role_vert_counts = {(row[0], row[1]): row[2] for row in db.execute(role_vert_stmt).all()}

        if usage == "assignment" and not authority_service.is_executive_or_admin(current_user.id):
            assigned_vids = authority_service.get_user_vertical_ids(current_user.id)
            all_verts = [org_service.get_vertical(vid) for vid in assigned_vids if vid]
        else:
            all_verts = org_service.list_verticals()

        all_roles = [
            ("SPORTS_CORE", "Sports Core", 5),
            ("DEPUTY_CORE", "Deputy Core", 4),
            ("SUPER_COORDINATOR", "Super Coordinator", 3),
            ("COORDINATOR", "Coordinator", 2),
            ("VOLUNTEER", "Volunteer", 1),
        ]
        actor_level = authority_service.get_user_operational_level(current_user.id)
        is_exec_or_admin = authority_service.is_executive_or_admin(current_user.id)

        combos = []
        for v in all_verts:
            if not v or (v.status != VerticalStatus.ACTIVE and usage == "assignment"):
                continue
            if vertical_id and v.id != vertical_id:
                continue
            for r_name, r_label, r_lvl in all_roles:
                if role_filter and r_name != role_filter:
                    continue
                if usage == "assignment":
                    if is_exec_or_admin:
                        if actor_level is not None and r_lvl >= actor_level:
                            continue
                    else:
                        if actor_level is None or r_lvl >= actor_level:
                            continue

                title = f"{v.name} → {r_label}s"
                cnt = role_vert_counts.get((v.id, r_name), 0)
                if search and search.strip():
                    s_lower = search.strip().lower()
                    if s_lower not in title.lower():
                        continue
                combos.append({
                    "id": f"{v.id}:{r_name}",
                    "vertical_id": str(v.id),
                    "vertical_name": v.name,
                    "role": r_name,
                    "role_label": r_label,
                    "title": title,
                    "member_count": cnt,
                })

        total = len(combos)
        paged = combos[offset : offset + limit]
        items = [
            SelectorItem(
                id=c["id"],
                type="ROLE_VERTICAL",
                label=c["title"],
                sublabel=f"{c['vertical_name']} • {c['member_count']} members",
                badge=c["role"],
                member_count=c["member_count"],
                metadata=c,
            )
            for c in paged
        ]
        groups = [
            SelectorGroupItem(
                type="role_vertical",
                id=c["id"],
                name=c["title"],
                member_count=c["member_count"],
                vertical_id=c["vertical_id"],
                role=c["role"],
                metadata=c,
            )
            for c in paged
        ]
        return SelectorResponse(selection_type=mode, total=total, items=items, groups=groups)

    # 4. ALL_USERS / ORGANIZATION AUDIENCE
    if mode in ("ALL_USERS", "ALL"):
        can_broadcast = authority_service.is_executive_or_admin(current_user.id)
        if not can_broadcast:
            return SelectorResponse(selection_type=mode, total=0, items=[], groups=[])

        if search and search.strip():
            s_low = search.strip().lower()
            keywords = ["all", "org", "organization", "member", "everyone", "broadcast"]
            if not any(k in s_low or s_low in k for k in keywords):
                return SelectorResponse(selection_type=mode, total=0, items=[], groups=[])

        total_org_users = db.scalar(select(func.count(User.id)).where(User.account_status == AccountStatus.ACTIVE)) or 0
        items = [
            SelectorItem(
                id="ALL",
                type="ALL",
                label="All Organization Members",
                sublabel=f"Organization-wide audience broadcast • {total_org_users} members",
                badge="ORGANIZATION",
                member_count=total_org_users,
                metadata={"scope": "ALL", "member_count": total_org_users},
            )
        ]
        groups = [
            SelectorGroupItem(
                type="organization",
                id="ALL",
                name="All Organization Members",
                member_count=total_org_users,
            )
        ]
        return SelectorResponse(selection_type=mode, total=1, items=items, groups=groups)

    # 5. EVENT_TEAM SELECTION
    if mode == "EVENT_TEAM":
        users = user_service.list_users(
            status_filter=AccountStatus.ACTIVE,
            search=search,
            role_filter="EVENT_TEAM",
            limit=limit,
            offset=offset,
        )
        total = user_service.count_users(
            status_filter=AccountStatus.ACTIVE,
            search=search,
            role_filter="EVENT_TEAM",
        )
        items = [
            SelectorItem(
                id=str(u.id),
                type="EVENT_TEAM",
                label=u.full_name or u.username,
                sublabel=f"@{u.username} • EVENT_TEAM",
                badge="EVENT_TEAM",
                metadata={"user_id": str(u.id), "role": "EVENT_TEAM"},
            )
            for u in users
        ]
        return SelectorResponse(selection_type=mode, total=total, items=items)

    # 6. USER / MULTI_USER SELECTION
    allowed_roles = None
    scoped_vertical_ids = None
    scoped_vertical_id = vertical_id
    allowed_user_ids = None

    actor_level = authority_service.get_user_operational_level(current_user.id)
    is_exec = authority_service.is_executive(current_user.id)
    is_admin = authority_service.is_admin(current_user.id)

    if usage == "assignment":
        if is_admin and not authority_service.is_internal_operational(current_user.id):
            return SelectorResponse(selection_type=mode, total=0, items=[], users=[])

        if actor_level is not None:
            allowed_roles = [
                r for r, lvl in INTERNAL_OPERATIONAL_HIERARCHY.items()
                if lvl < actor_level
            ]
            if len(allowed_roles) == 0:
                return SelectorResponse(selection_type=mode, total=0, items=[], users=[])

        if not is_exec:
            assigned_vids = authority_service.get_user_vertical_ids(current_user.id)
            if scoped_vertical_id:
                if scoped_vertical_id not in assigned_vids:
                    return SelectorResponse(selection_type=mode, total=0, items=[], users=[])
                scoped_vertical_ids = [scoped_vertical_id]
                scoped_vertical_id = None
            else:
                scoped_vertical_ids = assigned_vids
    else:
        if not authority_service.is_executive_or_admin(current_user.id):
            user_roles = authority_service.get_user_role_names(current_user.id)
            if "EVENT_TEAM" in user_roles:
                event_ids = authority_service.get_user_event_ids(current_user.id)
                from app.models.event import EventMember, EventTeamProfile
                member_uids = db.scalars(
                    select(EventMember.user_id).where(EventMember.event_id.in_(event_ids))
                ).all() if event_ids else []
                team_uids = db.scalars(
                    select(EventTeamProfile.user_id).where(EventTeamProfile.event_id.in_(event_ids))
                ).all() if event_ids else []
                allowed_user_ids = set(member_uids) | set(team_uids) | {current_user.id}
            else:
                # Non-executive, non-EVENT_TEAM internal user:
                # Only clamp to their own verticals when a specific vertical_id is
                # explicitly requested. Without a filter, show the full user universe
                # so selectors (POC, Head POC, etc.) are not artificially restricted.
                assigned_vids = authority_service.get_user_vertical_ids(current_user.id)
                if scoped_vertical_id:
                    if scoped_vertical_id not in assigned_vids:
                        scoped_vertical_ids = []
                        scoped_vertical_id = None
                    else:
                        scoped_vertical_ids = [scoped_vertical_id]
                        scoped_vertical_id = None
                # else: no vertical filter → leave scoped_vertical_ids as None (all users)

    users = user_service.list_users(
        status_filter=AccountStatus.ACTIVE,
        search=search,
        role_filter=role_filter,
        allowed_roles=allowed_roles,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
        allowed_user_ids=allowed_user_ids,
        limit=limit,
        offset=offset,
    )
    total = user_service.count_users(
        status_filter=AccountStatus.ACTIVE,
        search=search,
        role_filter=role_filter,
        allowed_roles=allowed_roles,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
        allowed_user_ids=allowed_user_ids,
    )

    if role_filter == "ADMIN":
        return SelectorResponse(selection_type=mode, total=0, items=[], users=[])

    items = []
    users_list = []
    for u in users:
        # Universal selector is strictly prohibited from showing or selecting ADMIN users
        roles = rbac_service.get_user_roles(u.id)
        role_names = [r.name for r in roles]
        if "ADMIN" in role_names:
            continue

        verts = org_service.get_user_verticals(u.id)
        role_str = roles[0].name if roles else "MEMBER"
        vert_str = verts[0][0].name if verts else "Unassigned"
        items.append(
            SelectorItem(
                id=str(u.id),
                type="USER",
                label=u.full_name or u.username,
                sublabel=f"@{u.username} • {role_str} • {vert_str}",
                badge=role_str,
                metadata={
                    "user_id": str(u.id),
                    "username": u.username,
                    "email": u.email,
                    "roles": role_names,
                    "vertical_ids": [str(v[0].id) for v in verts],
                },
            )
        )
        users_list.append(
            SelectorUserItem(
                id=str(u.id),
                username=u.username,
                full_name=u.full_name,
                email=u.email,
                role={"name": role_str},
                vertical={"id": str(verts[0][0].id), "name": vert_str} if verts else None,
                account_status=u.account_status.value,
            )
        )

    return SelectorResponse(selection_type=mode, total=total, items=items, users=users_list)


@router.post(
    "/resolve-audience",
    response_model=AudienceResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve Audience",
    description="Resolves audience group selections (entire organization, verticals, roles, combinations) and individual users into a deduplicated set of user IDs.",
)
def resolve_audience_options(
    request: AudienceResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceResolveResponse:
    from app.services.audience_service import AudienceService
    service = AudienceService(db)
    return service.resolve_audience(request, actor=current_user)

