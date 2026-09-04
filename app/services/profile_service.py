"""
Profile Service - User & Team Metadata Management
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User, UserAvailability, UserProfile
from app.schemas.profile import UserProfileResponse, UserProfileUpdate
from app.services.audit_service import AuditService


class ProfileService:
    """
    Service for managing normalized user profile operational metadata.
    """

    @staticmethod
    def get_or_create_profile(db: Session, user_id: uuid.UUID) -> UserProfile:
        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        profile = db.execute(stmt).scalar_one_or_none()

        if not profile:
            profile = UserProfile(
                user_id=user_id,
                specialization="",
                operational_capability="",
                certifications=[],
                availability=UserAvailability.AVAILABLE,
                profile_notes="",
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        return profile

    @staticmethod
    def update_profile(
        db: Session,
        user_id: uuid.UUID,
        data: UserProfileUpdate,
        actor_id: uuid.UUID,
    ) -> UserProfile:
        profile = ProfileService.get_or_create_profile(db, user_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(profile, key, value)

        # Audit log via AuditService
        audit_service = AuditService(db)
        audit_service.log(
            action="UPDATE_USER_PROFILE",
            resource_type="USER_PROFILE",
            resource_id=str(profile.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "target_user_id": str(user_id),
                "updated_fields": list(update_dict.keys()),
            },
        )
        db.commit()
        db.refresh(profile)

        return profile

    @staticmethod
    def format_profile_response(profile: UserProfile) -> UserProfileResponse:
        user = profile.user
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            username=user.username if user else None,
            full_name=user.full_name if user else None,
            email=user.email if user else None,
            account_created_at=user.created_at if user else None,
            phone_number=profile.phone_number,
            specialization=profile.specialization,
            operational_capability=profile.operational_capability,
            certifications=profile.certifications or [],
            availability=profile.availability,
            profile_notes=profile.profile_notes,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
