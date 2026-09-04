"""
FAQ & Operational Knowledge Base SQLAlchemy Model
Paradox Sports OMS - Phase 13
"""

import enum
import uuid
from typing import Optional
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FAQStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class FAQ(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faqs"

    question: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="General", index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[FAQStatus] = mapped_column(
        Enum(FAQStatus, name="faq_status_enum", native_enum=True),
        nullable=False,
        default=FAQStatus.PUBLISHED,
        index=True,
    )
    target_audience: Mapped[str] = mapped_column(String(50), nullable=False, default="ALL")
    related_route: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    route_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])

    def __repr__(self) -> str:
        return f"<FAQ(id={self.id}, question='{self.question[:30]}...', category='{self.category}', status='{self.status}')>"
