"""
Governance & System Configuration Models
Includes Resource Ownership Transfers and System Configuration.
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TransferResourceType(str, enum.Enum):
    ACCOUNT = "ACCOUNT"
    EVENT = "EVENT"
    TASK = "TASK"
    REQUIREMENT = "REQUIREMENT"


class TransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class OwnershipTransfer(Base, UUIDPrimaryKeyMixin):
    """Governed resource ownership and POC transfer protocol."""

    __tablename__ = "ownership_transfers"

    resource_type: Mapped[TransferResourceType] = mapped_column(
        Enum(TransferResourceType, name="transfer_resource_type_enum", native_enum=True),
        nullable=False,
    )
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    current_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewed_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus, name="transfer_status_enum", native_enum=True),
        nullable=False,
        default=TransferStatus.PENDING,
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    current_owner = relationship("User", foreign_keys=[current_owner_id], lazy="joined")
    requested_owner = relationship("User", foreign_keys=[requested_owner_id], lazy="joined")
    requested_by = relationship("User", foreign_keys=[requested_by_id], lazy="joined")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id], lazy="joined")

    __table_args__ = (
        Index("ix_transfers_resource", "resource_type", "resource_id"),
        Index("ix_transfers_status", "status"),
        Index("ix_transfers_current_owner", "current_owner_id"),
        Index("ix_transfers_requested_owner", "requested_owner_id"),
    )


class ConfigValueType(str, enum.Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"


class SystemConfig(Base, UUIDPrimaryKeyMixin):
    """Typed administrative system configuration repository (Secrets remain in environment)."""

    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[ConfigValueType] = mapped_column(
        Enum(ConfigValueType, name="config_value_type_enum", native_enum=True),
        nullable=False,
        default=ConfigValueType.STRING,
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    updated_by = relationship("User", foreign_keys=[updated_by_id], lazy="joined")

    __table_args__ = (
        Index("ix_system_configs_key_active", "key", "is_active"),
    )
