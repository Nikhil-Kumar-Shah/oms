"""
User Model, Account Lifecycle States & Team Profile Metadata
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class UserAvailability(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    ON_LEAVE = "ON_LEAVE"
    INACTIVE = "INACTIVE"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Authoritative OMS User Entity.
    Enforces zero hard deletion and explicit account lifecycle states.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique user handle (case-insensitive)",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
        doc="User email address",
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full display name of user",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Argon2id password hash",
    )

    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, length=20),
        default=AccountStatus.ACTIVE,
        nullable=False,
        index=True,
        doc="Current account lifecycle state",
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of last successful authentication",
    )

    disabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when account was transitioned to disabled/suspended/archived",
    )

    # Relationships
    sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    user_roles: Mapped[List["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    user_verticals: Mapped[List["UserVertical"]] = relationship(
        "UserVertical",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    permission_overrides: Mapped[List["UserPermissionOverride"]] = relationship(
        "UserPermissionOverride",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        return self.account_status == AccountStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', status='{self.account_status}')>"


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Structured Team/User Operational Profile Metadata.
    1:1 relationship with User.
    """

    __tablename__ = "user_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    phone_number = Column(String(50), nullable=True)
    specialization = Column(String(255), nullable=True)  # e.g., "Football Referee, Pitch Setup"
    operational_capability = Column(Text, nullable=True)  # e.g., "Event field setup, match recording"
    certifications = Column(JSONB, nullable=True, default=list)  # e.g., ["First Aid CPR", "FA Referee"]
    availability = Column(
        Enum(UserAvailability, name="user_availability_enum", native_enum=True),
        nullable=False,
        default=UserAvailability.AVAILABLE,
        index=True,
    )
    profile_notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id}, availability='{self.availability}')>"
