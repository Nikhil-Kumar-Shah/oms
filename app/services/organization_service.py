"""
Organization & Vertical Service
Manages organizational divisions and user-vertical assignments.
Hierarchy: Organization -> Vertical -> User (No Department concept)
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.schemas.organization import VerticalCreate, VerticalUpdate
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class OrganizationService:
    """Manages Organization and Vertical lifecycle."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def get_or_create_default_organization(self) -> Organization:
        """Retrieves or creates default Paradox Sports organization."""
        stmt = select(Organization).where(Organization.code == "PARADOX_SPORTS")
        org = self.db.scalar(stmt)
        if not org:
            org = Organization(
                name="Paradox Sports Department",
                code="PARADOX_SPORTS",
                description="Core operations management system organization",
            )
            self.db.add(org)
            self.db.flush()
            logger.info(f"Created default Organization: id={org.id}")
        return org

    def get_organization(self, org_id: Optional[uuid.UUID] = None) -> Organization:
        """Retrieves organization by ID or returns default."""
        if org_id:
            stmt = select(Organization).where(Organization.id == org_id).options(
                selectinload(Organization.verticals)
            )
            org = self.db.scalar(stmt)
            if not org:
                raise EntityNotFoundException("Organization", str(org_id))
            return org
        return self.get_or_create_default_organization()

    def create_vertical(self, data: VerticalCreate, org_id: Optional[uuid.UUID] = None) -> Vertical:
        """
        Creates a new vertical under the specified or default organization.
        Validates vertical name uniqueness within organization.
        """
        organization = self.get_organization(org_id or data.organization_id)
        name = data.name.strip()

        # Check name uniqueness
        stmt = select(Vertical).where(
            Vertical.organization_id == organization.id,
            Vertical.name == name,
        )
        if self.db.scalar(stmt):
            raise ValidationException(
                f"A vertical with the name '{name}' already exists in this organization"
            )

        vertical = Vertical(
            organization_id=organization.id,
            name=name,
            description=data.description.strip() if data.description else None,
            status=VerticalStatus.ACTIVE,
        )
        self.db.add(vertical)
        self.db.flush()
        logger.info(f"Created Vertical '{vertical.name}' (id={vertical.id})")
        return vertical

    def get_vertical(self, vertical_id: uuid.UUID) -> Vertical:
        """Retrieves vertical by UUID."""
        stmt = select(Vertical).where(Vertical.id == vertical_id)
        vertical = self.db.scalar(stmt)
        if not vertical:
            raise EntityNotFoundException("Vertical", str(vertical_id))
        return vertical

    def list_verticals(
        self,
        org_id: Optional[uuid.UUID] = None,
        status_filter: Optional[VerticalStatus] = None,
    ) -> List[Vertical]:
        """Lists verticals filtered by organization and optional lifecycle status."""
        stmt = select(Vertical).order_by(Vertical.name)
        if org_id:
            stmt = stmt.where(Vertical.organization_id == org_id)
        if status_filter:
            stmt = stmt.where(Vertical.status == status_filter)
        return list(self.db.scalars(stmt).all())

    def update_vertical(self, vertical_id: uuid.UUID, data: VerticalUpdate) -> Vertical:
        """Updates vertical attributes or lifecycle state."""
        vertical = self.get_vertical(vertical_id)
        if data.name is not None:
            name = data.name.strip()
            # Check unique constraint if name is modified
            if name != vertical.name:
                stmt = select(Vertical).where(
                    Vertical.organization_id == vertical.organization_id,
                    Vertical.name == name,
                )
                if self.db.scalar(stmt):
                    raise ValidationException(f"Vertical name '{name}' is already taken")
            vertical.name = name

        if data.description is not None:
            vertical.description = data.description.strip() if data.description else None

        if data.status is not None:
            vertical.status = data.status

        self.db.flush()
        logger.info(f"Updated Vertical {vertical_id} (status={vertical.status})")
        return vertical

    def assign_user_verticals(
        self,
        user_id: uuid.UUID,
        assignments: List[Dict[str, Any]],
    ) -> List[UserVertical]:
        """
        Assigns user to one or more verticals.
        Validates that target verticals exist and are ACTIVE.
        """
        # Delete existing user vertical assignments
        self.db.execute(delete(UserVertical).where(UserVertical.user_id == user_id))

        results = []
        for item in assignments:
            vert_id = item["vertical_id"]
            is_primary = item.get("is_primary", False)
            vertical = self.get_vertical(vert_id)

            if not vertical.is_active:
                raise ValidationException(
                    f"Cannot assign user to inactive or disabled vertical '{vertical.name}'"
                )

            assignment = UserVertical(
                user_id=user_id,
                vertical_id=vertical.id,
                is_primary=is_primary,
            )
            self.db.add(assignment)
            results.append(assignment)

        self.db.flush()
        logger.info(f"Assigned {len(results)} verticals to user {user_id}")
        return results

    def get_user_verticals(self, user_id: uuid.UUID) -> List[Tuple[Vertical, bool]]:
        """Returns list of (Vertical, is_primary) tuples assigned to a user."""
        stmt = (
            select(Vertical, UserVertical.is_primary)
            .join(UserVertical, UserVertical.vertical_id == Vertical.id)
            .where(UserVertical.user_id == user_id)
        )
        return list(self.db.execute(stmt).all())

    def disable_vertical(self, vertical_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> Vertical:
        """Disables a vertical division (non-destructive)."""
        vertical = self.get_vertical(vertical_id)
        vertical.status = VerticalStatus.DISABLED
        self.db.flush()
        self.audit.log(
            action="VERTICAL_DISABLE",
            resource_type="VERTICAL",
            resource_id=str(vertical.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"name": vertical.name, "status": vertical.status.value},
        )
        logger.info(f"Disabled Vertical '{vertical.name}' (id={vertical.id})")
        return vertical

    def archive_vertical(self, vertical_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> Vertical:
        """Archives a vertical division (non-destructive)."""
        vertical = self.get_vertical(vertical_id)
        vertical.status = VerticalStatus.ARCHIVED
        self.db.flush()
        self.audit.log(
            action="VERTICAL_ARCHIVE",
            resource_type="VERTICAL",
            resource_id=str(vertical.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"name": vertical.name, "status": vertical.status.value},
        )
        logger.info(f"Archived Vertical '{vertical.name}' (id={vertical.id})")
        return vertical

    def remove_user_from_vertical(
        self,
        user_id: uuid.UUID,
        vertical_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """
        Removes a user from a specific vertical division non-destructively.
        Does NOT delete the user account.
        """
        stmt = select(UserVertical).where(
            UserVertical.user_id == user_id,
            UserVertical.vertical_id == vertical_id,
        )
        assignment = self.db.scalar(stmt)
        if not assignment:
            raise EntityNotFoundException("UserVertical assignment", f"user={user_id}, vertical={vertical_id}")

        self.db.delete(assignment)
        self.db.flush()
        self.audit.log(
            action="VERTICAL_MEMBER_REMOVE",
            resource_type="USER_VERTICAL",
            resource_id=f"{user_id}:{vertical_id}",
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"user_id": str(user_id), "vertical_id": str(vertical_id)},
        )
        logger.info(f"Removed user {user_id} from vertical {vertical_id}")
