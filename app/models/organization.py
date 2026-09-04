"""
Organization & Vertical Models
Standardized Organizational Hierarchy:
Organization -> Vertical -> User (No Department concept)
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class VerticalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Authoritative Organization Entity.
    Top of the organization hierarchy.
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full name of the organization",
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique organization short code (e.g. PARADOX_SPORTS)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    verticals: Mapped[List["Vertical"]] = relationship(
        "Vertical",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, code='{self.code}', name='{self.name}')>"


class Vertical(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Authoritative Vertical Entity.
    Organizational divisions under an Organization.
    Zero-deletion policy enforced via lifecycle states.
    """

    __tablename__ = "verticals"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_verticals_org_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Vertical division name",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[VerticalStatus] = mapped_column(
        Enum(VerticalStatus, native_enum=False, length=20),
        default=VerticalStatus.ACTIVE,
        nullable=False,
        index=True,
        doc="Lifecycle state of the vertical",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="verticals",
    )

    user_assignments: Mapped[List["UserVertical"]] = relationship(
        "UserVertical",
        back_populates="vertical",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        return self.status == VerticalStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Vertical(id={self.id}, name='{self.name}', status='{self.status}')>"


class UserVertical(Base):
    """
    User-Vertical Assignment Mapping.
    Associates users to specific vertical scopes.
    """

    __tablename__ = "user_verticals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    vertical_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="CASCADE"),
        primary_key=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indicates user's primary vertical assignment",
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_verticals")
    vertical: Mapped["Vertical"] = relationship("Vertical", back_populates="user_assignments")

    def __repr__(self) -> str:
        return f"<UserVertical(user_id={self.user_id}, vertical_id={self.vertical_id})>"
