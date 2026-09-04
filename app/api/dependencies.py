"""
Server-Side Authorization & Authentication Dependencies
All security and authorization decisions are enforced server-authoritatively.
"""

import uuid
from typing import Callable, List, Optional, Set, Tuple
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationFailedException, ForbiddenException
from app.core.logging import get_logger
from app.models.session import UserSession
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

logger = get_logger(__name__)
settings = get_settings()


def extract_session_token(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Extracts raw session token from:
    1. Authorization: Bearer <token> header
    2. HttpOnly session cookie
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()

    cookie_val = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_val:
        return cookie_val.strip()

    return None


def get_current_user_and_session(
    request: Request,
    token: Optional[str] = Depends(extract_session_token),
    db: Session = Depends(get_db),
) -> Tuple[User, UserSession]:
    """
    Validates session token against PostgreSQL.
    Guarantees user exists, account is ACTIVE, and session is unexpired and unrevoked.
    """
    if not token:
        raise AuthenticationFailedException("Authentication required. Missing session token or cookie.")

    auth_service = AuthService(db)
    return auth_service.validate_session(token)


def get_current_user(
    user_and_session: Tuple[User, UserSession] = Depends(get_current_user_and_session),
) -> User:
    """Dependency returning the authenticated User entity."""
    return user_and_session[0]


def get_current_session(
    user_and_session: Tuple[User, UserSession] = Depends(get_current_user_and_session),
) -> UserSession:
    """Dependency returning the active UserSession entity."""
    return user_and_session[1]


def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory enforcing that the authenticated user possesses
    at least one of the specified canonical roles.
    ADMIN role always bypasses role checks.
    """

    def role_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        rbac_service = RbacService(db)
        user_roles = rbac_service.get_user_roles(user.id)
        role_names = {r.name for r in user_roles}

        if "ADMIN" in role_names:
            return user

        if not any(role in role_names for role in allowed_roles):
            logger.warning(
                f"Forbidden role access: User '{user.username}' with roles {role_names} "
                f"denied access (required: {allowed_roles})"
            )
            raise ForbiddenException(f"Action requires one of the following roles: {', '.join(allowed_roles)}")

        return user

    return role_checker


def require_permission(*required_permissions: str) -> Callable:
    """
    Dependency factory enforcing that the user possesses ALL specified
    effective permissions (Role permissions + explicit grants - explicit revokes).
    ADMIN role always possesses all permissions.
    """

    def permission_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        rbac_service = RbacService(db)
        effective_perms = rbac_service.get_effective_permissions(user.id)

        missing = [p for p in required_permissions if p not in effective_perms]
        if missing:
            logger.warning(
                f"Forbidden permission access: User '{user.username}' missing permissions: {missing}"
            )
            raise ForbiddenException(
                f"Missing required permission(s): {', '.join(missing)}"
            )

        return user

    return permission_checker


def require_vertical_scope(vertical_id: uuid.UUID) -> Callable:
    """
    Object-level authorization check:
    Ensures user is either an ADMIN/SPORTS_CORE executive OR is actively assigned
    to the target vertical division.
    """

    def scope_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        rbac_service = RbacService(db)
        user_roles = {r.name for r in rbac_service.get_user_roles(user.id)}

        # Leadership roles have broad cross-vertical operational access
        if "ADMIN" in user_roles or "SPORTS_CORE" in user_roles:
            return user

        # Check explicit vertical assignment
        org_service = OrganizationService(db)
        user_verticals = org_service.get_user_verticals(user.id)
        assigned_vids = {v.id for v, _ in user_verticals}

        if vertical_id not in assigned_vids:
            logger.warning(
                f"Scope violation: User '{user.username}' not assigned to vertical {vertical_id}"
            )
            raise ForbiddenException("You are not assigned to this vertical division")

        return user

    return scope_checker


def require_operational_level(min_level: int) -> Callable:
    """
    Dependency factory enforcing that the user possesses an internal operational
    level >= min_level (1=VOLUNTEER, 2=COORDINATOR, 3=SUPER_COORDINATOR, 4=DEPUTY_CORE, 5=SPORTS_CORE).
    """
    def level_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.services.authority_service import AuthorityService

        auth_service = AuthorityService(db)
        op_level = auth_service.get_user_operational_level(user.id)
        if op_level is None or op_level < min_level:
            logger.warning(
                f"Operational level denied: User '{user.username}' (Level {op_level}) "
                f"below required Level {min_level}"
            )
            raise ForbiddenException(f"Action requires minimum operational hierarchy Level {min_level}")
        return user

    return level_checker


def require_executive_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Enforces user is an executive (SPORTS_CORE or DEPUTY_CORE, Level >= 4)."""
    from app.services.authority_service import AuthorityService

    auth_service = AuthorityService(db)
    if not auth_service.is_executive(user.id):
        raise ForbiddenException("Action requires executive leadership authorization")
    return user


def require_admin_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Enforces user is a System Administrator."""
    from app.services.authority_service import AuthorityService

    auth_service = AuthorityService(db)
    if not auth_service.is_admin(user.id):
        raise ForbiddenException("Action requires system administrator authorization")
    return user


def require_object_access(
    object_type: str,
    id_param_name: str = "id",
    action: str = "read",
) -> Callable:
    """
    Reusable object-level authorization dependency.
    Evaluates path parameter corresponding to target resource UUID.
    """
    def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.services.authority_service import AuthorityService

        obj_id_str = request.path_params.get(id_param_name)
        if not obj_id_str:
            return user
        try:
            obj_id = uuid.UUID(str(obj_id_str))
        except ValueError:
            return user

        auth_service = AuthorityService(db)
        if not auth_service.can_access_object(user, object_type, obj_id, action=action):
            logger.warning(
                f"Object-level authorization denied: User '{user.username}' "
                f"cannot {action} {object_type} {obj_id}"
            )
            raise ForbiddenException(f"You do not have access to this {object_type}")
        return user

    return checker


# Convenient aliases
require_user_session = get_current_user


def require_permissions(permissions: List[str]) -> Callable:
    """Convenience list wrapper for require_permission."""
    return require_permission(*permissions)


