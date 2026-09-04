"""
User Management Service
Handles user creation, updates, lifecycle state transitions, and credentials.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set
from sqlalchemy import cast, func, or_, select, String
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_strength
from app.models.organization import UserVertical
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import AuditService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

logger = get_logger(__name__)


class UserService:
    """Manages user identity and account lifecycle."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.rbac = RbacService(db)
        self.org = OrganizationService(db)

    def create_user(
        self,
        data: UserCreate,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> User:
        """
        Creates a new user account within an explicit transaction.
        Validates username uniqueness, password policy, hashes password using Argon2id,
        and assigns initial roles and verticals.
        """
        username = data.username.strip().lower()
        validate_password_strength(data.password)

        # Check unique username
        stmt = select(User).where(User.username == username)
        if self.db.scalar(stmt):
            raise ValidationException(f"Username '{username}' is already registered")

        # Check unique email if provided
        if data.email:
            email = data.email.strip().lower()
            stmt = select(User).where(User.email == email)
            if self.db.scalar(stmt):
                raise ValidationException(f"Email '{email}' is already registered")
        else:
            email = None

        pwd_hash = hash_password(data.password)

        user = User(
            username=username,
            full_name=data.full_name.strip(),
            email=email,
            password_hash=pwd_hash,
            account_status=AccountStatus.ACTIVE,
        )
        self.db.add(user)
        self.db.flush()

        # Assign initial roles if provided
        if data.role_ids:
            self.rbac.assign_roles(user.id, data.role_ids)

        # Assign initial verticals if provided
        if data.vertical_ids:
            assignments = [{"vertical_id": vid, "is_primary": i == 0} for i, vid in enumerate(data.vertical_ids)]
            self.org.assign_user_verticals(user.id, assignments)

        # Audit creation
        self.audit.log(
            action="USER_CREATE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            correlation_id=correlation_id,
            details={"username": user.username, "full_name": user.full_name},
        )

        logger.info(f"Created User '{user.username}' (id={user.id})")
        return user

    def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """Retrieves user by UUID with roles and verticals preloaded."""
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals),
            )
            .where(User.id == user_id)
        )
        user = self.db.scalar(stmt)
        if not user:
            raise EntityNotFoundException("User", str(user_id))
        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Retrieves user by username (case-insensitive)."""
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals),
            )
            .where(func.lower(User.username) == username.strip().lower())
        )
        return self.db.scalar(stmt)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves user by email address (case-insensitive)."""
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals),
            )
            .where(func.lower(User.email) == email.strip().lower())
        )
        return self.db.scalar(stmt)

    def get_user_by_identifier(self, identifier: str) -> Optional[User]:
        """
        Retrieves user by username OR email address (case-insensitive).
        Enables seamless sign-in with either handle or registered email ID.
        """
        clean_id = identifier.strip().lower()
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles),
                selectinload(User.user_verticals),
            )
            .where(
                or_(
                    func.lower(User.username) == clean_id,
                    func.lower(User.email) == clean_id,
                )
            )
        )
        return self.db.scalar(stmt)

    def list_users(
        self,
        status_filter: Optional[AccountStatus] = None,
        search: Optional[str] = None,
        role_filter: Optional[str] = None,
        allowed_roles: Optional[List[str]] = None,
        vertical_id: Optional[uuid.UUID] = None,
        vertical_ids: Optional[List[uuid.UUID]] = None,
        allowed_user_ids: Optional[Set[uuid.UUID]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Lists users with optional account status, search query, role, vertical, and allowed_user_ids filters."""
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role),
                selectinload(User.user_verticals).selectinload(UserVertical.vertical),
            )
            .order_by(User.created_at.desc())
        )
        if status_filter:
            stmt = stmt.where(User.account_status == status_filter)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.username).ilike(term),
                    func.lower(User.full_name).ilike(term),
                    func.lower(User.email).ilike(term),
                    cast(User.id, String).ilike(term),
                )
            )
        if role_filter and role_filter.strip():
            stmt = stmt.join(User.user_roles).join(UserRole.role).where(Role.name == role_filter.strip().upper())
        elif allowed_roles is not None:
            if len(allowed_roles) == 0:
                return []
            stmt = stmt.join(User.user_roles).join(UserRole.role).where(Role.name.in_([r.upper() for r in allowed_roles]))
        if vertical_id:
            stmt = stmt.join(User.user_verticals).where(UserVertical.vertical_id == vertical_id)
        elif vertical_ids is not None:
            if len(vertical_ids) == 0:
                return []
            stmt = stmt.join(User.user_verticals).where(UserVertical.vertical_id.in_(vertical_ids))
        if allowed_user_ids is not None:
            if len(allowed_user_ids) == 0:
                return []
            stmt = stmt.where(User.id.in_(allowed_user_ids))

        stmt = stmt.distinct().offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_users(
        self,
        status_filter: Optional[AccountStatus] = None,
        search: Optional[str] = None,
        role_filter: Optional[str] = None,
        allowed_roles: Optional[List[str]] = None,
        vertical_id: Optional[uuid.UUID] = None,
        vertical_ids: Optional[List[uuid.UUID]] = None,
        allowed_user_ids: Optional[Set[uuid.UUID]] = None,
    ) -> int:
        """Returns total user count matching query criteria."""
        stmt = select(func.count(func.distinct(User.id)))
        if status_filter:
            stmt = stmt.where(User.account_status == status_filter)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.username).ilike(term),
                    func.lower(User.full_name).ilike(term),
                    func.lower(User.email).ilike(term),
                    cast(User.id, String).ilike(term),
                )
            )
        if role_filter and role_filter.strip():
            stmt = stmt.join(User.user_roles).join(UserRole.role).where(Role.name == role_filter.strip().upper())
        elif allowed_roles is not None:
            if len(allowed_roles) == 0:
                return 0
            stmt = stmt.join(User.user_roles).join(UserRole.role).where(Role.name.in_([r.upper() for r in allowed_roles]))
        if vertical_id:
            stmt = stmt.join(User.user_verticals).where(UserVertical.vertical_id == vertical_id)
        elif vertical_ids is not None:
            if len(vertical_ids) == 0:
                return 0
            stmt = stmt.join(User.user_verticals).where(UserVertical.vertical_id.in_(vertical_ids))
        if allowed_user_ids is not None:
            if len(allowed_user_ids) == 0:
                return 0
            stmt = stmt.where(User.id.in_(allowed_user_ids))

        return self.db.scalar(stmt) or 0

    def update_user(
        self,
        user_id: uuid.UUID,
        data: UserUpdate,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> User:
        """Updates user profile details."""
        user = self.get_user_by_id(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name.strip()

        if data.email is not None:
            email = data.email.strip().lower() if data.email else None
            if email != user.email:
                if email:
                    stmt = select(User).where(User.email == email, User.id != user.id)
                    if self.db.scalar(stmt):
                        raise ValidationException(f"Email '{email}' is already taken")
                user.email = email

        self.audit.log(
            action="USER_UPDATE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            correlation_id=correlation_id,
            details={"full_name": user.full_name, "email": user.email},
        )
        self.db.flush()
        return user

    def disable_user(
        self,
        user_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> User:
        """
        Transitions user account to DISABLED.
        Revokes all active sessions immediately.
        Enforces zero hard deletion.
        """
        user = self.get_user_by_id(user_id)
        user.account_status = AccountStatus.DISABLED
        user.disabled_at = datetime.now(timezone.utc)

        # Invalidate all active user sessions
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        active_sessions = self.db.scalars(stmt).all()
        now = datetime.now(timezone.utc)
        for s in active_sessions:
            s.revoked_at = now

        self.audit.log(
            action="USER_DISABLE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            correlation_id=correlation_id,
            details={"revoked_sessions": len(active_sessions)},
        )
        self.db.flush()
        logger.info(f"Disabled user {user.username} (revoked {len(active_sessions)} sessions)")
        return user

    def enable_user(
        self,
        user_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> User:
        """Transitions user account back to ACTIVE."""
        user = self.get_user_by_id(user_id)
        user.account_status = AccountStatus.ACTIVE
        user.disabled_at = None

        self.audit.log(
            action="USER_ENABLE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        self.db.flush()
        logger.info(f"Enabled user {user.username}")
        return user

    def admin_reset_password(
        self,
        user_id: uuid.UUID,
        new_password: str,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Administrative password reset.
        Updates password hash and revokes all active sessions.
        """
        user = self.get_user_by_id(user_id)
        validate_password_strength(new_password)

        user.password_hash = hash_password(new_password)

        # Invalidate existing sessions
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        for s in self.db.scalars(stmt).all():
            s.revoked_at = datetime.now(timezone.utc)

        self.audit.log(
            action="ADMIN_PASSWORD_RESET",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        self.db.flush()
        logger.info(f"Admin reset password for user {user.username}")
