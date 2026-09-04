"""
Authentication API Endpoints
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from app.api.dependencies import extract_session_token, get_current_session, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import (
    AuthSuccessResponse,
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    SessionInfo,
    UserRoleInfo,
    UserVerticalInfo,
)
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates credentials and creates a persistent server-side session.",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSuccessResponse:
    auth_service = AuthService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    correlation_id = request.headers.get("X-Request-ID")

    user, session, raw_token = auth_service.login(
        username=payload.username,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )
    db.commit()

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
    )

    # Build User Profile Details
    user_roles = rbac_service.get_user_roles(user.id)
    effective_perms = list(rbac_service.get_effective_permissions(user.id))
    user_verticals = org_service.get_user_verticals(user.id)

    roles_info = [UserRoleInfo(id=r.id, name=r.name, description=r.description) for r in user_roles]
    verts_info = [UserVerticalInfo(id=v.id, name=v.name, is_primary=p) for v, p in user_verticals]

    me_data = MeResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        account_status=user.account_status,
        roles=roles_info,
        effective_permissions=sorted(effective_perms),
        verticals=verts_info,
        last_login_at=user.last_login_at,
    )

    session_info = SessionInfo(
        session_id=session.id,
        token=raw_token,
        expires_at=session.expires_at,
    )

    return AuthSuccessResponse(
        success=True,
        session=session_info,
        user=me_data,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes current session and clears session cookie.",
)
def logout(
    request: Request,
    response: Response,
    token: str = Depends(extract_session_token),
    db: Session = Depends(get_db),
):
    if token:
        auth_service = AuthService(db)
        correlation_id = request.headers.get("X-Request-ID")
        ip_address = request.client.host if request.client else None
        auth_service.logout(token, correlation_id=correlation_id, ip_address=ip_address)
        db.commit()

    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return {"success": True, "message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Current Authenticated User",
    description="Returns current authenticated user, roles, effective permissions, and verticals.",
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)

    user_roles = rbac_service.get_user_roles(current_user.id)
    effective_perms = list(rbac_service.get_effective_permissions(current_user.id))
    user_verticals = org_service.get_user_verticals(current_user.id)

    roles_info = [UserRoleInfo(id=r.id, name=r.name, description=r.description) for r in user_roles]
    verts_info = [UserVerticalInfo(id=v.id, name=v.name, is_primary=p) for v, p in user_verticals]

    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        account_status=current_user.account_status,
        roles=roles_info,
        effective_permissions=sorted(effective_perms),
        verticals=verts_info,
        last_login_at=current_user.last_login_at,
    )


@router.get(
    "/context",
    status_code=status.HTTP_200_OK,
    summary="Get Authoritative Operational Context",
    description="Returns current user's authoritative role hierarchy level, assigned verticals, capabilities, and operational scope.",
)
def get_auth_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService

    authority_service = AuthorityService(db)
    return authority_service.build_auth_context(current_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Changes password for authenticated user. Verifies current password before updating.",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    correlation_id = request.headers.get("X-Request-ID")
    ip_address = request.client.host if request.client else None

    auth_service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        current_session_id=current_session.id,
        correlation_id=correlation_id,
        ip_address=ip_address,
    )
    db.commit()
    return {"success": True, "message": "Password changed successfully"}
