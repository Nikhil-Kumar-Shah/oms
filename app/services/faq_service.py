"""
FAQ Service Layer
Paradox Sports OMS - Phase 13
"""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException
from app.core.logging import get_logger
from app.models.faq import FAQ, FAQStatus
from app.models.user import User
from app.schemas.faq import FAQCreate, FAQUpdate
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class FAQService:
    """Manages FAQ & Operational Reference Knowledge Base."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def create_faq(self, data: FAQCreate, actor_id: UUID) -> FAQ:
        faq = FAQ(
            question=data.question.strip(),
            answer=data.answer.strip(),
            category=data.category.strip(),
            display_order=data.display_order,
            status=data.status,
            target_audience=data.target_audience,
            related_route=data.related_route,
            route_label=data.route_label,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        self.db.add(faq)
        self.db.flush()

        self.audit.log(
            action="FAQ_CREATE",
            resource_type="FAQ",
            resource_id=str(faq.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"question": faq.question, "category": faq.category},
        )
        logger.info(f"Created FAQ '{faq.question[:30]}...' (id={faq.id})")
        return faq

    def get_faq_by_id(self, faq_id: UUID) -> FAQ:
        faq = self.db.scalar(
            select(FAQ)
            .where(FAQ.id == faq_id)
            .options(selectinload(FAQ.created_by), selectinload(FAQ.updated_by))
        )
        if not faq:
            raise EntityNotFoundException(f"FAQ with ID '{faq_id}' not found")
        return faq

    def list_faqs(
        self,
        category: Optional[str] = None,
        status: Optional[FAQStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[FAQ], int]:
        stmt = select(FAQ).options(selectinload(FAQ.created_by))
        count_stmt = select(func.count(FAQ.id))

        if category and category != "ALL":
            stmt = stmt.where(FAQ.category == category)
            count_stmt = count_stmt.where(FAQ.category == category)

        if status:
            stmt = stmt.where(FAQ.status == status)
            count_stmt = count_stmt.where(FAQ.status == status)

        if search and search.strip():
            q = f"%{search.strip()}%"
            stmt = stmt.where(
                (FAQ.question.ilike(q)) | (FAQ.answer.ilike(q)) | (FAQ.category.ilike(q))
            )
            count_stmt = count_stmt.where(
                (FAQ.question.ilike(q)) | (FAQ.answer.ilike(q)) | (FAQ.category.ilike(q))
            )

        total = self.db.scalar(count_stmt) or 0
        faqs = list(
            self.db.scalars(
                stmt.order_by(FAQ.display_order.asc(), FAQ.created_at.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return faqs, total

    def update_faq(self, faq_id: UUID, data: FAQUpdate, actor_id: UUID) -> FAQ:
        faq = self.get_faq_by_id(faq_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(faq, key, value)
        faq.updated_by_id = actor_id

        self.audit.log(
            action="FAQ_UPDATE",
            resource_type="FAQ",
            resource_id=str(faq.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return faq

    def delete_faq(self, faq_id: UUID, actor_id: UUID) -> bool:
        faq = self.get_faq_by_id(faq_id)
        self.db.delete(faq)
        self.audit.log(
            action="FAQ_DELETE",
            resource_type="FAQ",
            resource_id=str(faq_id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"question": faq.question},
        )
        return True
