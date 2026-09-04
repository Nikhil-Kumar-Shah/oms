"""
User & Team Profile API Routes
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_db, require_permission
from app.models.user import User
from app.schemas.profile import UserProfileResponse, UserProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["User Profiles"])


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves current authenticated user's operational profile."""
    profile = ProfileService.get_or_create_profile(db, current_user.id)
    return ProfileService.format_profile_response(profile)


@router.put("/me", response_model=UserProfileResponse)
@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates current authenticated user's operational profile."""
    profile = ProfileService.update_profile(db, current_user.id, data, current_user.id)
    return ProfileService.format_profile_response(profile)


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user_profile(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves specified user's operational profile within authorized vertical scope."""
    from app.services.authority_service import AuthorityService
    from app.core.exceptions import ForbiddenException

    auth_service = AuthorityService(db)
    if not auth_service.is_executive_or_admin(current_user.id):
        if not auth_service.can_access_object(current_user, "user", user_id):
            raise ForbiddenException("You do not have access to view this user profile")

    try:
        profile = ProfileService.get_or_create_profile(db, user_id)
        return ProfileService.format_profile_response(profile)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{user_id}", response_model=UserProfileResponse)
@router.patch("/{user_id}", response_model=UserProfileResponse)
def update_user_profile(
    user_id: uuid.UUID,
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """Updates specified user's operational profile (Admin / Supervisor only)."""
    try:
        profile = ProfileService.update_profile(db, user_id, data, current_user.id)
        return ProfileService.format_profile_response(profile)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
