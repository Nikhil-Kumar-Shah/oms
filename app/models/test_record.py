"""
Verification Model: SystemTestRecord
Temporary foundation model to verify:
FastAPI -> SQLAlchemy -> PostgreSQL -> Transaction -> Persistence -> Retrieval
"""

from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemTestRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Temporary foundation verification table.
    Proves complete database persistence and transaction lifecycle.
    """

    __tablename__ = "system_test_records"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Name of the test record",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of the test record",
    )

    def __repr__(self) -> str:
        return f"<SystemTestRecord(id={self.id}, name='{self.name}')>"
