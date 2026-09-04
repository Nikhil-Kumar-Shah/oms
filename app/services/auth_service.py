"""
Authentication & Session Management Service
Server-authoritative login, session lifecycle, and credential operations.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.core.config import get_settings
from app.core.exceptions import (
    AccountInactiveException,
    AuthenticationFailedException,
    SessionExpiredException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_password_strength,
    verify_password,
)
from app.models.rbac import UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.services.audit_service import AuditService
from app.services.rbac_service import RbacService
from app.services.user_service import UserService

logger = get_logger(__name__)
settings = get_settings()

# In-memory session validation cache: token_hash -> (user, session, expiry_mono)
# Drastically reduces DB query latency for rapid/concurrent API calls (e.g., polling, dashboard mounts).
_SESSION_CACHE: Dict[str, Tuple[User, UserSession, float]] = {}


def invalidate_session_cache(token_hash: Optional[str] = None) -> None:
    """Invalidates the in-memory session cache."""
    if token_hash:
        _SESSION_CACHE.pop(token_hash, None)
    else:
        _SESSION_CACHE.clear()


class AuthService:
    """Manages authentication, persistent sessions, and credential verification."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.users = UserService(db)
        self.rbac = RbacService(db)

    def login(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[User, UserSession, str]:
        """
        Authenticates user credentials using Argon2id.
        Verifies account is in ACTIVE state.
        Creates server-recognized persistent session with SHA-256 token hash.
        Returns (User, UserSession, raw_session_token).
        """
        user = self.users.get_user_by_identifier(username)

        # Constant-time / generic failure handling (do not reveal if username vs password was wrong)
        if not user or not verify_password(password, user.password_hash):
            self.audit.log(
                action="AUTH_LOGIN",
                resource_type="AUTH",
                outcome="FAILURE",
                correlation_id=correlation_id,
                ip_address=ip_address,
                details={"attempted_identifier": username},
            )
            raise AuthenticationFailedException("Invalid username or password")

        # Verify account status
        if user.account_status != AccountStatus.ACTIVE:
            self.audit.log(
                action="AUTH_LOGIN",
                resource_type="USER",
                resource_id=str(user.id),
                outcome="DENIED",
                actor_id=user.id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                details={"account_status": user.account_status.value},
            )
            raise AccountInactiveException(user.account_status.value)

        # Enforce Event Team full activation requirements (Event & Head POC assigned by Core)
        user_roles = {r.name for r in self.rbac.get_user_roles(user.id)}
        if "EVENT_TEAM" in user_roles and "ADMIN" not in user_roles and "SPORTS_CORE" not in user_roles:
            from app.services.event_team_service import EventTeamService
            evt_service = EventTeamService(self.db)
            is_active, reason = evt_service.is_event_team_fully_activated(user.id)
            if not is_active:
                self.audit.log(
                    action="AUTH_LOGIN",
                    resource_type="USER",
                    resource_id=str(user.id),
                    outcome="DENIED",
                    actor_id=user.id,
                    correlation_id=correlation_id,
                    ip_address=ip_address,
                    details={"reason": f"Event Team unactivated: {reason}"},
                )
                raise AccountInactiveException(f"PENDING_ACTIVATION: {reason}")

        # Generate secure random token
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.SESSION_EXPIRE_HOURS)

        session = UserSession(
            user_id=user.id,
            session_token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(session)

        # Update last login timestamp
        user.last_login_at = now

        # Audit successful login
        self.audit.log(
            action="AUTH_LOGIN",
            resource_type="SESSION",
            resource_id=str(session.id),
            outcome="SUCCESS",
            actor_id=user.id,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )

        self.db.flush()
        logger.info(f"User '{user.username}' logged in successfully (session_id={session.id})")
        return user, session, raw_token

    def logout(
        self,
        raw_token: str,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Revokes authenticated session."""
        if not raw_token:
            return

        token_hash = hash_session_token(raw_token)
        invalidate_session_cache(token_hash)
        stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
        session = self.db.scalar(stmt)

        if session and session.revoked_at is None:
            session.revoke()
            self.audit.log(
                action="AUTH_LOGOUT",
                resource_type="SESSION",
                resource_id=str(session.id),
                outcome="SUCCESS",
                actor_id=session.user_id,
                correlation_id=correlation_id,
                ip_address=ip_address,
            )
            self.db.flush()
            logger.info(f"Session {session.id} revoked on logout")

    def validate_session(self, raw_token: str) -> Tuple[User, UserSession]:
        """
        Validates session token:
        - Checks in-memory cache first (45s TTL) for fast sub-millisecond response.
        - Validates against PostgreSQL using eager joined loading.
        - Verifies session validity, unexpired status, and ACTIVE account.
        - Throttles last_seen_at write to at most once per 5 minutes.
        """
        if not raw_token:
            raise AuthenticationFailedException("Authentication required")

        token_hash = hash_session_token(raw_token)
        now_mono = time.monotonic()

        # 1. Check in-memory validation cache
        cached = _SESSION_CACHE.get(token_hash)
        if cached:
            c_user, c_session, expiry_mono = cached
            if now_mono < expiry_mono:
                if c_session.is_valid and c_user.account_status == AccountStatus.ACTIVE:
                    user_in_db = self.db.merge(c_user, load=False) if c_user not in self.db else c_user
                    session_in_db = self.db.merge(c_session, load=False) if c_session not in self.db else c_session
                    return user_in_db, session_in_db
                else:
                    _SESSION_CACHE.pop(token_hash, None)

        # 2. Database query with eager joined loading of user and user_roles
        stmt = (
            select(UserSession)
            .options(
                joinedload(UserSession.user).options(
                    selectinload(User.user_roles).selectinload(UserRole.role)
                )
            )
            .where(UserSession.session_token_hash == token_hash)
        )
        session = self.db.scalar(stmt)

        if not session:
            _SESSION_CACHE.pop(token_hash, None)
            raise AuthenticationFailedException("Invalid or unrecognized session token")

        if not session.is_valid:
            _SESSION_CACHE.pop(token_hash, None)
            raise SessionExpiredException("Session has expired or was revoked")

        user = session.user
        if not user:
            user = self.users.get_user_by_id(session.user_id)

        if user.account_status != AccountStatus.ACTIVE:
            _SESSION_CACHE.pop(token_hash, None)
            session.revoke()
            self.db.flush()
            raise AccountInactiveException(user.account_status.value)

        # Enforce Event Team full activation requirements (session invalidated if deactivated)
        user_roles = {ur.role.name for ur in user.user_roles if ur.role}
        if "EVENT_TEAM" in user_roles and "ADMIN" not in user_roles and "SPORTS_CORE" not in user_roles:
            from app.services.event_team_service import EventTeamService
            evt_service = EventTeamService(self.db)
            is_active, reason = evt_service.is_event_team_fully_activated(user.id)
            if not is_active:
                _SESSION_CACHE.pop(token_hash, None)
                session.revoke()
                self.db.flush()
                raise AccountInactiveException(f"PENDING_ACTIVATION: {reason}")

        # Touch last_seen_at only if >= 5 minutes elapsed (avoids write query on every GET)
        now = datetime.now(timezone.utc)
        if session.last_seen_at is None or (now - session.last_seen_at).total_seconds() > 300:
            session.touch()
            self.db.flush()

        # Cache session in memory for 45 seconds
        _SESSION_CACHE[token_hash] = (user, session, now_mono + 45.0)

        return user, session

    def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
        current_session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Verifies current password before updating to new Argon2id hash.
        Revokes other active sessions.
        """
        user = self.users.get_user_by_id(user_id)

        if not verify_password(current_password, user.password_hash):
            self.audit.log(
                action="AUTH_PASSWORD_CHANGE",
                resource_type="USER",
                resource_id=str(user.id),
                outcome="FAILURE",
                actor_id=user.id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                details={"reason": "Incorrect current password"},
            )
            raise ValidationException("Current password verification failed")

        validate_password_strength(new_password)
        user.password_hash = hash_password(new_password)

        # Invalidate all other sessions except current
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if current_session_id:
            stmt = stmt.where(UserSession.id != current_session_id)

        other_sessions = self.db.scalars(stmt).all()
        now = datetime.now(timezone.utc)
        for s in other_sessions:
            s.revoked_at = now

        self.audit.log(
            action="AUTH_PASSWORD_CHANGE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=user.id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            details={"revoked_sessions": len(other_sessions)},
        )
        self.db.flush()
        logger.info(f"Password changed for user {user.username} (revoked {len(other_sessions)} other sessions)")
