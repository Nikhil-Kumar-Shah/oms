"""
Administrative API Endpoints
All endpoints require server-authoritative role or permission authorization.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission, require_role
from app.core.database import get_db
from app.models.user import AccountStatus, User
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.schemas.governance import (
    SystemConfigCreate,
    SystemConfigListResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.schemas.organization import (
    AssignVerticalsRequest,
    VerticalCreate,
    VerticalResponse,
    VerticalUpdate,
)
from app.schemas.rbac import (
    AssignRolesRequest,
    PermissionResponse,
    RoleResponse,
    SetPermissionOverridesRequest,
)
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResetPasswordRequest,
    UserResponse,
    UserRoleSummary,
    UserUpdate,
    UserVerticalSummary,
)
from app.services.audit_service import AuditService
from app.services.config_service import SystemConfigService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Administration"])


# -----------------------------------------------------------------------------
# User Management
# -----------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Users",
    description="Lists all user accounts with their assigned roles and verticals within authorized scope.",
    dependencies=[Depends(require_permission("users.read"))],
)
def list_users(
    status_filter: Optional[AccountStatus] = Query(None),
    search: Optional[str] = Query(None, description="Search term for username, full name, or email"),
    role_filter: Optional[str] = Query(None, description="Filter by canonical role name"),
    vertical_id: Optional[UUID] = Query(None, description="Filter by vertical division"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserListResponse:
    from app.services.authority_service import AuthorityService

    user_service = UserService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)
    auth_service = AuthorityService(db)

    scoped_vertical_id = vertical_id
    scoped_vertical_ids = None

    if not auth_service.is_executive_or_admin(current_user.id):
        user_vids = auth_service.get_user_vertical_ids(current_user.id)
        if not user_vids:
            return UserListResponse(total=0, items=[])
        if scoped_vertical_id:
            if scoped_vertical_id not in user_vids:
                return UserListResponse(total=0, items=[])
        else:
            scoped_vertical_ids = user_vids

    users = user_service.list_users(
        status_filter=status_filter,
        search=search,
        role_filter=role_filter,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
        limit=limit,
        offset=offset,
    )
    total = user_service.count_users(
        status_filter=status_filter,
        search=search,
        role_filter=role_filter,
        vertical_id=scoped_vertical_id,
        vertical_ids=scoped_vertical_ids,
    )

    items = []
    for u in users:
        roles = [ur.role for ur in u.user_roles if ur.role] if hasattr(u, "user_roles") and u.user_roles else rbac_service.get_user_roles(u.id)
        verts = [(uv.vertical, uv.is_primary) for uv in u.user_verticals if uv.vertical] if hasattr(u, "user_verticals") and u.user_verticals else org_service.get_user_verticals(u.id)
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


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Account",
    description="Creates a new user account with initial roles and vertical assignments.",
    dependencies=[Depends(require_permission("users.create"))],
)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    user_service = UserService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)
    correlation_id = request.headers.get("X-Request-ID")

    user = user_service.create_user(
        data=payload,
        actor_id=current_user.id,
        correlation_id=correlation_id,
    )
    db.commit()

    roles = rbac_service.get_user_roles(user.id)
    verts = org_service.get_user_verticals(user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        account_status=user.account_status,
        roles=[UserRoleSummary(id=r.id, name=r.name) for r in roles],
        verticals=[UserVerticalSummary(id=v.id, name=v.name, is_primary=p) for v, p in verts],
        last_login_at=user.last_login_at,
        disabled_at=user.disabled_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Detail",
    description="Retrieves full user detail by UUID within authorized scope.",
    dependencies=[Depends(require_permission("users.read"))],
)
def get_user_detail(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    auth_service = AuthorityService(db)
    if not auth_service.is_executive_or_admin(current_user.id):
        if not auth_service.can_access_object(current_user, "user", user_id):
            raise ForbiddenException("You do not have access to view this user profile")

    user_service = UserService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)

    user = user_service.get_user_by_id(user_id)
    roles = rbac_service.get_user_roles(user.id)
    verts = org_service.get_user_verticals(user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        account_status=user.account_status,
        roles=[UserRoleSummary(id=r.id, name=r.name) for r in roles],
        verticals=[UserVerticalSummary(id=v.id, name=v.name, is_primary=p) for v, p in verts],
        last_login_at=user.last_login_at,
        disabled_at=user.disabled_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="Updates user display name and email address.",
    dependencies=[Depends(require_permission("users.update"))],
)
def update_user_profile(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService

    auth_service = AuthorityService(db)
    if not auth_service.is_executive_or_admin(current_user.id):
        if current_user.id != user_id:
            raise ForbiddenException("You cannot update other users' profile details")

    user_service = UserService(db)
    correlation_id = request.headers.get("X-Request-ID")

    user = user_service.update_user(
        user_id=user_id,
        data=payload,
        actor_id=current_user.id,
        correlation_id=correlation_id,
    )
    db.commit()
    return get_user_detail(user.id, current_user=current_user, db=db)



@router.post(
    "/users/{user_id}/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable User Account",
    description="Sets account status to DISABLED and revokes all active sessions immediately.",
    dependencies=[Depends(require_permission("users.disable"))],
)
def disable_user_account(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    correlation_id = request.headers.get("X-Request-ID")
    user = user_service.disable_user(user_id=user_id, actor_id=current_user.id, correlation_id=correlation_id)
    db.commit()
    return {"success": True, "message": f"User {user.username} has been disabled."}


@router.post(
    "/users/{user_id}/enable",
    status_code=status.HTTP_200_OK,
    summary="Enable User Account",
    description="Restores user account status to ACTIVE.",
    dependencies=[Depends(require_permission("users.update"))],
)
def enable_user_account(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    correlation_id = request.headers.get("X-Request-ID")
    user = user_service.enable_user(user_id=user_id, actor_id=current_user.id, correlation_id=correlation_id)
    db.commit()
    return {"success": True, "message": f"User {user.username} has been activated."}


@router.post(
    "/users/{user_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Set User Account Status",
    description="Transitions user account status (ACTIVE, DISABLED, SUSPENDED).",
    dependencies=[Depends(require_permission("users.update"))],
)
def set_user_status(
    user_id: UUID,
    new_status: AccountStatus = Query(..., description="Target account status"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    correlation_id = request.headers.get("X-Request-ID") if request else None
    if new_status == AccountStatus.DISABLED:
        user = user_service.disable_user(user_id=user_id, actor_id=current_user.id, correlation_id=correlation_id)
    elif new_status == AccountStatus.ACTIVE:
        user = user_service.enable_user(user_id=user_id, actor_id=current_user.id, correlation_id=correlation_id)
    else:
        user = user_service.get_user_by_id(user_id)
        user.account_status = new_status
        db.flush()
    db.commit()
    return {"success": True, "account_status": user.account_status.value, "message": f"User {user.username} status set to {user.account_status.value}."}


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Admin Password Reset",
    description="Sets a new password for target user and invalidates their existing sessions.",
    dependencies=[Depends(require_permission("users.update"))],
)
def reset_user_password(
    user_id: UUID,
    payload: UserResetPasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    correlation_id = request.headers.get("X-Request-ID")
    user_service.admin_reset_password(
        user_id=user_id,
        new_password=payload.new_password,
        actor_id=current_user.id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {"success": True, "message": "Password reset successfully."}


@router.post(
    "/users/{user_id}/roles",
    status_code=status.HTTP_200_OK,
    summary="Assign User Roles",
    description="Replaces user role assignments.",
    dependencies=[Depends(require_permission("roles.manage"))],
)
def assign_user_roles(
    user_id: UUID,
    payload: AssignRolesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rbac_service = RbacService(db)
    audit_service = AuditService(db)
    correlation_id = request.headers.get("X-Request-ID")

    roles = rbac_service.assign_roles(user_id=user_id, role_ids=payload.role_ids)
    audit_service.log(
        action="ROLE_ASSIGN",
        resource_type="USER",
        resource_id=str(user_id),
        outcome="SUCCESS",
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={"assigned_roles": [r.name for r in roles]},
    )
    db.commit()
    return {"success": True, "roles": [r.name for r in roles]}


@router.post(
    "/users/{user_id}/verticals",
    status_code=status.HTTP_200_OK,
    summary="Assign User Verticals",
    description="Replaces user vertical assignments.",
    dependencies=[Depends(require_permission("verticals.assign"))],
)
def assign_user_verticals(
    user_id: UUID,
    payload: AssignVerticalsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_service = OrganizationService(db)
    audit_service = AuditService(db)
    correlation_id = request.headers.get("X-Request-ID")

    assignments = [{"vertical_id": item.vertical_id, "is_primary": item.is_primary} for item in payload.assignments]
    org_service.assign_user_verticals(user_id=user_id, assignments=assignments)

    audit_service.log(
        action="USER_VERTICAL_ASSIGN",
        resource_type="USER",
        resource_id=str(user_id),
        outcome="SUCCESS",
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={"assigned_count": len(assignments)},
    )
    db.commit()
    return {"success": True, "message": "Verticals assigned successfully."}


@router.post(
    "/users/{user_id}/permissions",
    status_code=status.HTTP_200_OK,
    summary="Set Explicit Permission Overrides",
    description="Grants or revokes explicit permissions for a user.",
    dependencies=[Depends(require_permission("permissions.manage"))],
)
def set_permission_overrides(
    user_id: UUID,
    payload: SetPermissionOverridesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rbac_service = RbacService(db)
    audit_service = AuditService(db)
    correlation_id = request.headers.get("X-Request-ID")

    overrides = [{"permission_id": item.permission_id, "is_granted": item.is_granted} for item in payload.overrides]
    rbac_service.set_permission_overrides(user_id=user_id, overrides=overrides)

    audit_service.log(
        action="PERMISSION_OVERRIDE_SET",
        resource_type="USER",
        resource_id=str(user_id),
        outcome="SUCCESS",
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={"overrides_count": len(overrides)},
    )
    db.commit()
    return {"success": True, "message": "Permission overrides updated."}


# -----------------------------------------------------------------------------
# Vertical Management
# -----------------------------------------------------------------------------

@router.get(
    "/verticals",
    response_model=List[VerticalResponse],
    status_code=status.HTTP_200_OK,
    summary="List Verticals (Admin)",
    description="Lists all organizational vertical divisions for administrative inspection.",
    dependencies=[Depends(require_permission("verticals.read"))],
)
def list_admin_verticals(
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[VerticalResponse]:
    from app.models.organization import VerticalStatus
    org_service = OrganizationService(db)
    st = VerticalStatus(status_filter) if status_filter and status_filter != "ALL" else None
    verticals = org_service.list_verticals(status_filter=st)
    return [VerticalResponse.model_validate(v) for v in verticals]


@router.post(
    "/verticals",
    response_model=VerticalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Vertical Division (Admin)",
    description="Creates a new vertical division.",
    dependencies=[Depends(require_permission("verticals.create"))],
)
@router.post(
    "/organization/verticals",
    response_model=VerticalResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[Depends(require_permission("verticals.create"))],
)
def create_vertical(
    payload: VerticalCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    org_service = OrganizationService(db)
    audit_service = AuditService(db)
    correlation_id = request.headers.get("X-Request-ID")

    vertical = org_service.create_vertical(payload)
    audit_service.log(
        action="VERTICAL_CREATE",
        resource_type="VERTICAL",
        resource_id=str(vertical.id),
        outcome="SUCCESS",
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={"name": vertical.name},
    )
    db.commit()
    return VerticalResponse.model_validate(vertical)


@router.patch(
    "/verticals/{vertical_id}",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Vertical Division (Admin)",
    description="Updates vertical attributes or lifecycle state.",
    dependencies=[Depends(require_permission("verticals.update"))],
)
@router.patch(
    "/organization/verticals/{vertical_id}",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(require_permission("verticals.update"))],
)
def update_vertical(
    vertical_id: UUID,
    payload: VerticalUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    org_service = OrganizationService(db)
    audit_service = AuditService(db)
    correlation_id = request.headers.get("X-Request-ID")

    vertical = org_service.update_vertical(vertical_id, payload)
    audit_service.log(
        action="VERTICAL_UPDATE",
        resource_type="VERTICAL",
        resource_id=str(vertical.id),
        outcome="SUCCESS",
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={"name": vertical.name, "status": vertical.status.value},
    )
    db.commit()
    return VerticalResponse.model_validate(vertical)


@router.post(
    "/verticals/{vertical_id}/disable",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable Vertical Division (Admin)",
    description="Disables a vertical division non-destructively.",
    dependencies=[Depends(require_permission("verticals.disable"))],
)
@router.post(
    "/organization/verticals/{vertical_id}/disable",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(require_permission("verticals.disable"))],
)
def disable_vertical(
    vertical_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    org_service = OrganizationService(db)
    vertical = org_service.disable_vertical(vertical_id, actor_id=current_user.id)
    db.commit()
    return VerticalResponse.model_validate(vertical)


@router.post(
    "/verticals/{vertical_id}/archive",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive Vertical Division (Admin)",
    description="Archives a vertical division non-destructively.",
    dependencies=[Depends(require_permission("verticals.disable"))],
)
@router.post(
    "/organization/verticals/{vertical_id}/archive",
    response_model=VerticalResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(require_permission("verticals.disable"))],
)
def archive_vertical(
    vertical_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    org_service = OrganizationService(db)
    vertical = org_service.archive_vertical(vertical_id, actor_id=current_user.id)
    db.commit()
    return VerticalResponse.model_validate(vertical)


@router.delete(
    "/users/{user_id}/verticals/{vertical_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove User From Vertical",
    description="Removes a user's assignment from a vertical division without deleting user entity.",
    dependencies=[Depends(require_permission("verticals.assign"))],
)
def remove_user_vertical(
    user_id: UUID,
    vertical_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_service = OrganizationService(db)
    org_service.remove_user_from_vertical(user_id=user_id, vertical_id=vertical_id, actor_id=current_user.id)
    db.commit()
    return {"success": True, "message": "User removed from vertical successfully."}


# -----------------------------------------------------------------------------
# RBAC Metadata & Audit Center
# -----------------------------------------------------------------------------

@router.get(
    "/roles",
    response_model=List[RoleResponse],
    status_code=status.HTTP_200_OK,
    summary="List Canonical Roles",
    description="Retrieves all system roles and their assigned permissions.",
    dependencies=[Depends(require_permission("roles.read"))],
)
def list_roles(db: Session = Depends(get_db)) -> List[RoleResponse]:
    rbac_service = RbacService(db)
    roles = rbac_service.list_roles()
    results = []
    for r in roles:
        perms = [PermissionResponse.model_validate(rp.permission) for rp in r.role_permissions]
        results.append(
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                permissions=perms,
            )
        )
    return results


@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Permission Registry",
    description="Retrieves all system permission definitions.",
    dependencies=[Depends(require_permission("permissions.read"))],
)
def list_permissions(db: Session = Depends(get_db)) -> List[PermissionResponse]:
    rbac_service = RbacService(db)
    perms = rbac_service.list_permissions()
    return [PermissionResponse.model_validate(p) for p in perms]


def _format_audit_log_response(log) -> AuditLogResponse:
    return AuditLogResponse(
        id=log.id,
        timestamp=log.timestamp,
        created_at=log.timestamp,
        actor_id=log.actor_id,
        actor_username=log.actor.username if log.actor else None,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        outcome=log.outcome,
        correlation_id=log.correlation_id,
        ip_address=log.ip_address,
        details=log.details,
    )


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Immutable Audit Logs",
    description="Retrieves append-only audit records.",
    dependencies=[Depends(require_permission("audit.read"))],
)
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(None),
    actor_id: Optional[UUID] = Query(None),
    resource_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    audit_service = AuditService(db)
    logs = audit_service.list_logs(limit=limit, offset=offset, action=action, actor_id=actor_id, resource_type=resource_type, outcome=outcome)
    total = audit_service.count()
    return AuditLogListResponse(
        total=total,
        items=[_format_audit_log_response(log) for log in logs],
    )


# -----------------------------------------------------------------------------
# System Configuration
# -----------------------------------------------------------------------------

def _format_config_response(c) -> SystemConfigResponse:
    return SystemConfigResponse(
        id=c.id,
        key=c.key,
        value=c.value,
        value_type=c.value_type,
        description=c.description,
        is_active=c.is_active,
        updated_by_id=c.updated_by_id,
        updated_by_username=c.updated_by.username if c.updated_by else None,
        updated_at=c.updated_at,
    )


@router.get(
    "/config",
    response_model=SystemConfigListResponse,
    status_code=status.HTTP_200_OK,
    summary="List System Configurations",
    dependencies=[Depends(require_permission("config.read"))],
)
def list_system_configs(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> SystemConfigListResponse:
    service = SystemConfigService(db)
    configs = service.list_configs(is_active=is_active)
    return SystemConfigListResponse(
        total=len(configs),
        items=[_format_config_response(c) for c in configs],
    )


@router.post(
    "/config",
    response_model=SystemConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create System Configuration Parameter",
    dependencies=[Depends(require_permission("config.update"))],
)
def create_system_config(
    payload: SystemConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemConfigResponse:
    service = SystemConfigService(db)
    config = service.create_config(payload, actor_id=current_user.id)
    db.commit()
    return _format_config_response(service.get_config_by_id(config.id))


@router.get(
    "/config/{key}",
    response_model=SystemConfigResponse,
    dependencies=[Depends(require_permission("config.read"))],
)
def get_system_config(
    key: str,
    db: Session = Depends(get_db),
) -> SystemConfigResponse:
    service = SystemConfigService(db)
    return _format_config_response(service.get_config_by_key(key))


@router.patch(
    "/config/{key}",
    response_model=SystemConfigResponse,
    dependencies=[Depends(require_permission("config.update"))],
)
def update_system_config(
    key: str,
    payload: SystemConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemConfigResponse:
    service = SystemConfigService(db)
    config = service.update_config(key, payload, actor_id=current_user.id)
    db.commit()
    return _format_config_response(service.get_config_by_id(config.id))


# -----------------------------------------------------------------------------
# System Health & Diagnostic Telemetry
# -----------------------------------------------------------------------------

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Admin System Health & Diagnostics",
    description="Returns detailed administrative telemetry including database pool and latency.",
    dependencies=[Depends(require_permission("system.read"))],
)
def get_admin_system_health(
    db: Session = Depends(get_db),
):
    from app.core.database import engine
    from app.core.health import get_app_health, get_database_health

    app_health = get_app_health()
    db_health = get_database_health()

    pool_stats = {}
    try:
        pool = engine.pool
        pool_stats = {
            "size": pool.size() if hasattr(pool, "size") else 5,
            "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else 0,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else 0,
            "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
        }
    except Exception as e:
        pool_stats = {"status": "pool_inspect_error", "detail": str(e)}

    return {
        "status": db_health.get("status", "healthy"),
        "latency_ms": db_health.get("latency_ms", 0),
        "application": app_health,
        "database": {
            "status": db_health.get("status", "healthy"),
            "latency_ms": db_health.get("latency_ms", 0),
            "pool": pool_stats,
            "engine": str(engine.url.drivername if hasattr(engine, "url") else "postgresql+psycopg2"),
        },
        "timestamp": app_health.get("timestamp"),
    }

