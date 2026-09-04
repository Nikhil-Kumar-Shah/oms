"""
Service Layer for SystemTestRecord
Encapsulates CRUD operations, transaction boundaries, and business rules.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import EntityNotFoundException
from app.core.logging import get_logger
from app.models.test_record import SystemTestRecord
from app.schemas.test_record import SystemTestRecordCreate, SystemTestRecordUpdate

logger = get_logger(__name__)


class SystemTestRecordService:
    """Service handling operations for SystemTestRecord verification entity."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: SystemTestRecordCreate) -> SystemTestRecord:
        """
        Creates a new SystemTestRecord within an explicit transaction.
        Commits upon success or rolls back on error.
        """
        record = SystemTestRecord(
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
        )
        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            logger.info(f"Created SystemTestRecord: id={record.id}, name='{record.name}'")
            return record
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to create SystemTestRecord, transaction rolled back: {exc}")
            raise

    def get_by_id(self, record_id: UUID) -> SystemTestRecord:
        """
        Retrieves a SystemTestRecord by its UUID primary key.
        Raises EntityNotFoundException if not found.
        """
        stmt = select(SystemTestRecord).where(SystemTestRecord.id == record_id)
        record = self.db.scalar(stmt)
        if not record:
            logger.warning(f"SystemTestRecord not found: id={record_id}")
            raise EntityNotFoundException("SystemTestRecord", str(record_id))
        return record

    def list_all(self, limit: int = 100, offset: int = 0) -> List[SystemTestRecord]:
        """Lists all SystemTestRecords ordered by created_at desc."""
        stmt = (
            select(SystemTestRecord)
            .order_by(SystemTestRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """Returns total count of test records."""
        stmt = select(SystemTestRecord)
        return len(list(self.db.scalars(stmt).all()))

    def update(self, record_id: UUID, data: SystemTestRecordUpdate) -> SystemTestRecord:
        """Updates an existing test record."""
        record = self.get_by_id(record_id)
        try:
            if data.name is not None:
                record.name = data.name.strip()
            if data.description is not None:
                record.description = data.description.strip()
            self.db.commit()
            self.db.refresh(record)
            logger.info(f"Updated SystemTestRecord: id={record.id}")
            return record
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to update SystemTestRecord {record_id}, rolled back: {exc}")
            raise

    def delete_for_test(self, record_id: UUID) -> None:
        """
        TEMPORARY verification delete helper.
        Note: This is isolated for test record verification only.
        The actual Paradox OMS architecture adheres to a strict Zero-Deletion policy.
        """
        record = self.get_by_id(record_id)
        try:
            self.db.delete(record)
            self.db.commit()
            logger.info(f"Deleted test record {record_id} for foundation verification")
        except Exception as exc:
            self.db.rollback()
            raise
