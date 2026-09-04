"""
User Session Model
Database-backed persistent session model storing SHA-256 token hashes.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class UserSession(Base, UUIDPrimaryKeyMixin):
    """
    Persistent server-side authenticated session.
    Stores SHA-256 hash of token to prevent token theft from database compromise.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="SHA-256 hash of the bearer/cookie session token",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Session expiration timestamp",
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="Timestamp of last activity on this session",
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Revocation timestamp if manually logged out or invalidated",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        doc="Client IP address for audit and security",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Client User-Agent header",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
    )

    @property
    def is_valid(self) -> bool:
        """Determines if the session is currently valid, unexpired, and unrevoked."""
        now = datetime.now(timezone.utc)
        return self.revoked_at is None and self.expires_at > now

    def revoke(self) -> None:
        """Revokes the session immediately."""
        self.revoked_at = datetime.now(timezone.utc)

    def touch(self) -> None:
        """Updates last_seen_at timestamp."""
        self.last_seen_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, valid={self.is_valid})>"
