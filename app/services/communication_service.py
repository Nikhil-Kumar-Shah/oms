from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.communication import CommunicationLog, CommunicationLogStatus, CommunicationType
from app.models.event import Event
from app.models.organization import Vertical
from app.schemas.communication import CommunicationLogCreate, CommunicationLogUpdate
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class CommunicationLogService:
    """Manages operational communication tracker records."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def create_log(self, data: CommunicationLogCreate, created_by_id: UUID) -> CommunicationLog:
        if data.vertical_id:
            vert = self.db.get(Vertical, data.vertical_id)
            if not vert:
                raise ValidationException("Target vertical not found")

        if data.event_id:
            evt = self.db.get(Event, data.event_id)
            if not evt:
                raise ValidationException("Target event not found")

        log = CommunicationLog(
            date_time=data.date_time or datetime.now(timezone.utc),
            communication_type=data.communication_type,
            subject=data.subject,
            sender_info=data.sender_info,
            recipient_info=data.recipient_info,
            vertical_id=data.vertical_id,
            event_id=data.event_id,
            related_resource_type=data.related_resource_type,
            related_resource_id=data.related_resource_id,
            reference_link=data.reference_link,
            remarks=data.remarks,
            created_by_id=created_by_id,
            status=CommunicationLogStatus.RECORDED,
        )
        self.db.add(log)
        self.db.flush()

        self.audit.log(
            action="COMMUNICATION_LOG_CREATE",
            resource_type="COMMUNICATION_LOG",
            resource_id=str(log.id),
            outcome="SUCCESS",
            actor_id=created_by_id,
            details={"subject": log.subject, "type": log.communication_type.value},
        )
        logger.info(f"Created CommunicationLog '{log.subject}' (id={log.id})")
        return log

    def get_log_by_id(self, log_id: UUID) -> CommunicationLog:
        log = self.db.scalar(
            select(CommunicationLog)
            .where(CommunicationLog.id == log_id)
            .options(
                selectinload(CommunicationLog.created_by),
                selectinload(CommunicationLog.vertical),
                selectinload(CommunicationLog.event),
            )
        )
        if not log:
            raise EntityNotFoundException(f"Communication log '{log_id}' not found")
        return log

    def list_logs(
        self,
        vertical_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        communication_type: Optional[CommunicationType] = None,
        status: Optional[CommunicationLogStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CommunicationLog], int]:
        stmt = select(CommunicationLog).options(
            selectinload(CommunicationLog.created_by),
            selectinload(CommunicationLog.vertical),
            selectinload(CommunicationLog.event),
        )
        count_stmt = select(func.count(CommunicationLog.id))

        if vertical_id:
            stmt = stmt.where(CommunicationLog.vertical_id == vertical_id)
            count_stmt = count_stmt.where(CommunicationLog.vertical_id == vertical_id)
        if event_id:
            stmt = stmt.where(CommunicationLog.event_id == event_id)
            count_stmt = count_stmt.where(CommunicationLog.event_id == event_id)
        if communication_type:
            stmt = stmt.where(CommunicationLog.communication_type == communication_type)
            count_stmt = count_stmt.where(CommunicationLog.communication_type == communication_type)
        if status:
            stmt = stmt.where(CommunicationLog.status == status)
            count_stmt = count_stmt.where(CommunicationLog.status == status)

        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(stmt.order_by(CommunicationLog.date_time.desc()).offset(offset).limit(limit)).all())
        return items, total

    def update_log(self, log_id: UUID, data: CommunicationLogUpdate, actor_id: UUID) -> CommunicationLog:
        log = self.get_log_by_id(log_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(log, key, value)

        self.audit.log(
            action="COMMUNICATION_LOG_UPDATE",
            resource_type="COMMUNICATION_LOG",
            resource_id=str(log.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return log
