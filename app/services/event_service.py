"""
Events, Event Team & Readiness Service Layer
Server-authoritative event management, team coordination, readiness tracking & operational dashboard aggregation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.calendar import CalendarEntry
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventReadinessItem,
    EventStatus,
    EventTeamProfile,
    ReadinessCategory,
    ReadinessStatus,
)
from app.models.issue import Issue, IssueSensitivity
from app.models.meeting import Meeting
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import AccountStatus, User
from app.schemas.event import (
    EventAssignPOCRequest,
    EventCreate,
    EventMemberCreate,
    EventMemberUpdate,
    EventReadinessUpdate,
    EventTransitionRequest,
    EventUpdate,
    POCGroupAssignRequest,
    POCGroupResponse,
    POCMemberSummary,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)

DEFAULT_READINESS_CHECKPOINTS = [
    (ReadinessCategory.PLANNING, "Event Concept & Operational Scope Signed Off", "Clear event objectives and venue confirmed."),
    (ReadinessCategory.COORDINATION, "Event Head & Primary POC Assigned", "Lead coordinators designated and briefed."),
    (ReadinessCategory.DOCUMENTATION, "Schedule & Activity Timeline Prepared", "Chronological itinerary drafted and reviewed."),
    (ReadinessCategory.COMMUNICATIONS, "Internal & External Communications Sent", "Participant notices and promotional briefings issued."),
    (ReadinessCategory.TECHNICAL_PREPARATION, "Equipment & Venue Technical Prep", "Hardware, scoreboards, turf/court verified ready."),
    (ReadinessCategory.MOCK_TRIAL, "Dry Run / Rehearsal Conducted", "Operational run-through executed."),
    (ReadinessCategory.FINAL_APPROVAL, "Executive Core Leadership Final Sign-Off", "Sports Core sign-off obtained."),
    (ReadinessCategory.EXECUTION_READINESS, "Event Day Operational Readiness Confirmed", "All staff, materials, and emergency protocols deployed."),
]


class EventService:
    """Manages Events, Event Teams, Readiness Checkpoints, and Aggregated Dashboards."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def _validate_user_in_vertical(self, user_id: UUID, vertical_id: UUID, field_name: str = "User"):
        user = self.db.get(User, user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            raise ValidationException(f"{field_name} must exist and have ACTIVE account status")

        # Disallow EVENT_TEAM accounts from being assigned as internal POCs
        user_roles = set(self.db.scalars(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        ).all())
        if "EVENT_TEAM" in user_roles:
            raise ValidationException(f"Cannot assign {field_name.lower()}: Event Team accounts cannot be assigned as internal POCs")

        assignment = self.db.scalar(
            select(UserVertical).where(
                UserVertical.user_id == user_id,
                UserVertical.vertical_id == vertical_id,
            )
        )
        if not assignment:
            raise ValidationException(f"Cannot assign {field_name.lower()}: User '{user.username}' is not assigned to the target vertical division")
        return user

    def create_event(self, data: EventCreate, actor_id: UUID) -> Event:
        """
        Creates an operational event and connects external Event Team / contacts atomically.
        """
        vertical = self.db.get(Vertical, data.vertical_id)
        if not vertical or vertical.status != VerticalStatus.ACTIVE:
            raise ValidationException("Target vertical division must exist and be ACTIVE")

        # 1. Instantiate Event record
        resource_links = dict(data.resource_links or {})
        if data.event_head_name or data.event_head_phone or data.event_head_email:
            resource_links["event_head"] = {
                "name": data.event_head_name,
                "phone": data.event_head_phone,
                "email": data.event_head_email,
            }
        if data.additional_pocs:
            resource_links["additional_pocs"] = data.additional_pocs

        head_id = data.event_head_user_id or data.event_head_id
        poc_id = data.poc_head_user_id or data.primary_poc_user_id or data.primary_poc_id or head_id

        event = Event(
            vertical_id=data.vertical_id,
            name=data.name,
            description=data.description,
            event_type=data.event_type,
            status=EventStatus.PLANNING,
            planned_date=data.planned_date,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location,
            society_name=data.society_name,
            event_head_id=head_id,
            primary_poc_id=poc_id,
            created_by_id=actor_id,
            resource_links=resource_links,
            remarks=data.remarks,
        )
        self.db.add(event)
        self.db.flush()

        # Attach additional internal POC members
        if data.additional_poc_user_ids:
            for uid in data.additional_poc_user_ids:
                if uid != head_id and uid != poc_id:
                    # Check if already added
                    existing_mem = self.db.scalars(
                        select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == uid)
                    ).first()
                    if not existing_mem:
                        member = EventMember(
                            event_id=event.id,
                            user_id=uid,
                            role_in_event=EventMemberRole.POC,
                            assigned_by_id=actor_id,
                        )
                        self.db.add(member)

        # 2. Initialize Default Readiness Checkpoints
        for category, title, description in DEFAULT_READINESS_CHECKPOINTS:
            item = EventReadinessItem(
                event_id=event.id,
                category=category,
                title=title,
                description=description,
                status=ReadinessStatus.NOT_STARTED,
            )
            self.db.add(item)

        # 3. Associate External Event Team Account & Profile (Phase 10E)
        if data.event_team_user_id:
            team_user = self.db.get(User, data.event_team_user_id)
            if not team_user or team_user.account_status != AccountStatus.ACTIVE:
                raise ValidationException("Associated Event Team account must exist and be ACTIVE")

            # Verify target account has EVENT_TEAM role
            role_names = set(self.db.scalars(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == team_user.id)
            ).all())
            if "EVENT_TEAM" not in role_names:
                raise ValidationException(f"User '{team_user.username}' does not have the EVENT_TEAM role")

            # Look up or create EventTeamProfile
            profile = self.db.scalar(
                select(EventTeamProfile).where(EventTeamProfile.user_id == team_user.id)
            )
            if profile:
                profile.event_id = event.id
                if data.event_head_name:
                    profile.head_name = data.event_head_name.strip()
                if data.event_head_phone:
                    profile.head_phone = data.event_head_phone.strip()
                if data.event_head_email:
                    profile.head_email = data.event_head_email.strip()
                if data.additional_pocs is not None:
                    profile.members_summary = data.additional_pocs
                if data.society_name:
                    profile.team_name = profile.team_name or data.society_name.strip()
            else:
                profile = EventTeamProfile(
                    user_id=team_user.id,
                    event_id=event.id,
                    team_name=(data.society_name or data.name or team_user.full_name or team_user.username).strip(),
                    head_name=data.event_head_name.strip() if data.event_head_name else None,
                    head_phone=data.event_head_phone.strip() if data.event_head_phone else None,
                    head_email=data.event_head_email.strip() if data.event_head_email else None,
                    members_summary=data.additional_pocs or [],
                )
                self.db.add(profile)
            self.db.flush()

        # 4. Optional Legacy Internal POC assignment
        if data.event_head_id:
            head_user = self.db.get(User, data.event_head_id)
            if head_user and head_user.account_status == AccountStatus.ACTIVE:
                self.db.add(EventMember(
                    event_id=event.id,
                    user_id=head_user.id,
                    role_in_event=EventMemberRole.HEAD,
                    status=EventMemberStatus.ACTIVE,
                    assigned_by_id=actor_id,
                    notes="Assigned as Event Head at creation",
                ))
        if poc_id and poc_id != data.event_head_id:
            poc_user = self.db.get(User, poc_id)
            if poc_user and poc_user.account_status == AccountStatus.ACTIVE:
                existing_poc = self.db.scalars(
                    select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == poc_user.id)
                ).first()
                if not existing_poc:
                    self.db.add(EventMember(
                        event_id=event.id,
                        user_id=poc_user.id,
                        role_in_event=EventMemberRole.POC,
                        status=EventMemberStatus.ACTIVE,
                        assigned_by_id=actor_id,
                        notes="Assigned as POC Head at creation",
                    ))

        self.audit.log(
            action="EVENT_CREATE",
            resource_type="EVENT",
            resource_id=str(event.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "name": event.name,
                "vertical_id": str(event.vertical_id),
                "planned_date": event.planned_date.isoformat() if event.planned_date else None,
                "event_team_user_id": str(data.event_team_user_id) if data.event_team_user_id else None,
            },
        )
        logger.info(f"Created Event '{event.name}' (id={event.id}, event_team_user_id={data.event_team_user_id})")
        return event

    def _validate_event_access(self, event_id: UUID, current_user: Optional[User]):
        """
        Enforces vertical isolation and event team boundary.
        """
        if not current_user:
            return

        from app.services.authority_service import AuthorityService
        auth_service = AuthorityService(self.db)
        
        event = self.db.get(Event, event_id)
        if not event:
            raise EntityNotFoundException(f"Event with ID '{event_id}' not found")

        if not auth_service.can_view_event(current_user, event):
            raise ForbiddenException("You do not have authorization to access this event")

    def get_event_by_id(self, event_id: UUID, current_user: Optional[User] = None) -> Event:
        self._validate_event_access(event_id, current_user)
        event = self.db.scalar(
            select(Event)
            .where(Event.id == event_id)
            .options(
                selectinload(Event.vertical),
                selectinload(Event.event_head),
                selectinload(Event.primary_poc),
                selectinload(Event.created_by),
                selectinload(Event.members).selectinload(EventMember.user),
                selectinload(Event.readiness_items),
            )
        )
        if not event:
            raise EntityNotFoundException(f"Event with ID '{event_id}' not found")
        return event

    def list_events(
        self,
        vertical_id: Optional[UUID] = None,
        status: Optional[EventStatus] = None,
        current_user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Event], int]:
        stmt = select(Event).options(
            selectinload(Event.vertical),
            selectinload(Event.event_head),
            selectinload(Event.primary_poc),
            selectinload(Event.created_by),
        )
        count_stmt = select(func.count(Event.id))

        if current_user:
            from app.services.authority_service import AuthorityService
            auth_service = AuthorityService(self.db)
            if not auth_service.is_executive_or_admin(current_user.id):
                user_roles = auth_service.get_user_role_names(current_user.id)
                user_event_ids = auth_service.get_user_event_ids(current_user.id)
                if "EVENT_TEAM" in user_roles:
                    if not user_event_ids:
                        return [], 0
                    stmt = stmt.where(Event.id.in_(user_event_ids))
                    count_stmt = count_stmt.where(Event.id.in_(user_event_ids))
                else:
                    user_vids = auth_service.get_user_vertical_ids(current_user.id)
                    if vertical_id:
                        if vertical_id not in user_vids:
                            return [], 0
                    else:
                        scope_filter = or_(
                            Event.vertical_id.in_(user_vids),
                            Event.id.in_(user_event_ids),
                        ) if user_vids or user_event_ids else False
                        stmt = stmt.where(scope_filter)
                        count_stmt = count_stmt.where(scope_filter)

        if vertical_id:
            stmt = stmt.where(Event.vertical_id == vertical_id)
            count_stmt = count_stmt.where(Event.vertical_id == vertical_id)
        if status:
            stmt = stmt.where(Event.status == status)
            count_stmt = count_stmt.where(Event.status == status)

        total = self.db.scalar(count_stmt) or 0
        events = list(self.db.scalars(stmt.order_by(Event.planned_date.desc()).offset(offset).limit(limit)).all())
        return events, total

    def update_event(self, event_id: UUID, data: EventUpdate, actor_id: UUID) -> Event:
        event = self.get_event_by_id(event_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(event, key, value)

        self.audit.log(
            action="EVENT_UPDATE",
            resource_type="EVENT",
            resource_id=str(event.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return event

    def transition_event_status(self, event_id: UUID, data: EventTransitionRequest, actor_id: UUID) -> Event:
        event = self.get_event_by_id(event_id)
        old_status = event.status
        new_status = data.status

        # Strict authoritative state machine per Product Specification
        VALID_TRANSITIONS = {
            EventStatus.PLANNING: {EventStatus.NOT_STARTED, EventStatus.IN_PROGRESS, EventStatus.CANCELLED},
            EventStatus.NOT_STARTED: {EventStatus.IN_PROGRESS, EventStatus.CANCELLED},
            EventStatus.IN_PROGRESS: {EventStatus.COMPLETED, EventStatus.CANCELLED},
            EventStatus.COMPLETED: {EventStatus.ARCHIVED},
            EventStatus.CANCELLED: {EventStatus.ARCHIVED},
            EventStatus.ARCHIVED: set(),
        }

        if new_status != old_status and new_status not in VALID_TRANSITIONS.get(old_status, set()):
            allowed = [s.value for s in VALID_TRANSITIONS.get(old_status, set())]
            raise ValidationException(
                f"Invalid event status transition from {old_status.value} to {new_status.value}. "
                f"Allowed transitions from {old_status.value}: {allowed}"
            )

        event.status = new_status
        if data.remarks:
            event.remarks = f"{event.remarks or ''}\n[Status: {new_status.value}] {data.remarks}".strip()

        self.audit.log(
            action="EVENT_STATUS_TRANSITION",
            resource_type="EVENT",
            resource_id=str(event.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"old_status": old_status.value, "new_status": new_status.value, "remarks": data.remarks},
        )
        return event

    def assign_poc(self, event_id: UUID, data: EventAssignPOCRequest, actor_id: UUID) -> Event:
        event = self.get_event_by_id(event_id)

        if data.event_head_id is not None:
            if data.event_head_id:
                self._validate_user_in_vertical(data.event_head_id, event.vertical_id, "Event Head")
                # Add/update in EventMember
                member = self.db.scalar(select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == data.event_head_id))
                if not member:
                    self.db.add(EventMember(event_id=event.id, user_id=data.event_head_id, role_in_event=EventMemberRole.HEAD, assigned_by_id=actor_id))
                else:
                    member.role_in_event = EventMemberRole.HEAD
                    member.status = EventMemberStatus.ACTIVE
            event.event_head_id = data.event_head_id

        if data.primary_poc_id is not None:
            if data.primary_poc_id:
                self._validate_user_in_vertical(data.primary_poc_id, event.vertical_id, "Primary POC")
                member = self.db.scalar(select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == data.primary_poc_id))
                if not member:
                    self.db.add(EventMember(event_id=event.id, user_id=data.primary_poc_id, role_in_event=EventMemberRole.POC, assigned_by_id=actor_id))
                else:
                    member.role_in_event = EventMemberRole.POC
                    member.status = EventMemberStatus.ACTIVE
            event.primary_poc_id = data.primary_poc_id

        self.audit.log(
            action="EVENT_ASSIGN_POC",
            resource_type="EVENT",
            resource_id=str(event.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"event_head_id": str(event.event_head_id), "primary_poc_id": str(event.primary_poc_id)},
        )
        return event

    def assign_poc_group(self, event_id: UUID, data: POCGroupAssignRequest, actor_id: UUID) -> POCGroupResponse:
        """
        Assigns an authoritative POC Group to an Event.
        Enforces exactly 1 active Head POC and verifies all POC members in target vertical.
        """
        event = self.get_event_by_id(event_id)

        # 1. Validate exactly 1 active Head POC
        head_poc_user = self._validate_user_in_vertical(data.head_poc_id, event.vertical_id, "Head POC")
        event.primary_poc_id = data.head_poc_id

        head_member = self.db.scalar(
            select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == data.head_poc_id)
        )
        if not head_member:
            head_member = EventMember(
                event_id=event.id,
                user_id=data.head_poc_id,
                role_in_event=EventMemberRole.POC,
                status=EventMemberStatus.ACTIVE,
                assigned_by_id=actor_id,
                notes=data.notes,
            )
            self.db.add(head_member)
        else:
            head_member.role_in_event = EventMemberRole.POC
            head_member.status = EventMemberStatus.ACTIVE
            if data.notes:
                head_member.notes = data.notes

        # 2. Process additional POC members
        poc_member_summaries = []
        for poc_id in data.poc_member_ids:
            if poc_id == data.head_poc_id:
                continue
            poc_user = self._validate_user_in_vertical(poc_id, event.vertical_id, "POC Member")
            member = self.db.scalar(
                select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == poc_id)
            )
            if not member:
                member = EventMember(
                    event_id=event.id,
                    user_id=poc_id,
                    role_in_event=EventMemberRole.POC,
                    status=EventMemberStatus.ACTIVE,
                    assigned_by_id=actor_id,
                    notes=data.notes,
                )
                self.db.add(member)
            else:
                member.role_in_event = EventMemberRole.POC
                member.status = EventMemberStatus.ACTIVE

            poc_member_summaries.append(
                POCMemberSummary(
                    user_id=poc_user.id,
                    username=poc_user.username,
                    full_name=poc_user.full_name,
                    role_in_event=EventMemberRole.POC,
                    status=EventMemberStatus.ACTIVE,
                    notes=member.notes,
                )
            )

        self.db.flush()

        self.audit.log(
            action="EVENT_ASSIGN_POC_GROUP",
            resource_type="EVENT",
            resource_id=str(event.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "head_poc_id": str(data.head_poc_id),
                "head_poc_username": head_poc_user.username,
                "poc_member_count": len(poc_member_summaries),
            },
        )
        logger.info(f"Assigned POC Group to Event '{event.name}': Head={head_poc_user.username}, Members={len(poc_member_summaries)}")

        head_summary = POCMemberSummary(
            user_id=head_poc_user.id,
            username=head_poc_user.username,
            full_name=head_poc_user.full_name,
            role_in_event=EventMemberRole.POC,
            status=EventMemberStatus.ACTIVE,
            notes=head_member.notes,
        )

        return POCGroupResponse(
            event_id=event.id,
            event_name=event.name,
            vertical_id=event.vertical_id,
            head_poc=head_summary,
            poc_members=poc_member_summaries,
            total_poc_count=1 + len(poc_member_summaries),
        )

    def get_poc_group(self, event_id: UUID, current_user: Optional[User] = None) -> POCGroupResponse:
        """Retrieves active POC group for an Event."""
        self._validate_event_access(event_id, current_user)
        event = self.get_event_by_id(event_id, current_user=current_user)
        members = list(self.db.scalars(
            select(EventMember)
            .options(selectinload(EventMember.user))
            .where(
                EventMember.event_id == event.id,
                EventMember.role_in_event.in_([EventMemberRole.POC, EventMemberRole.HEAD]),
                EventMember.status == EventMemberStatus.ACTIVE,
            )
        ).all())

        head_summary = None
        poc_member_summaries = []

        for m in members:
            summary = POCMemberSummary(
                user_id=m.user_id,
                username=m.user.username if m.user else None,
                full_name=m.user.full_name if m.user else None,
                role_in_event=m.role_in_event,
                status=m.status,
                notes=m.notes,
            )
            if event.primary_poc_id and m.user_id == event.primary_poc_id:
                head_summary = summary
            else:
                poc_member_summaries.append(summary)

        return POCGroupResponse(
            event_id=event.id,
            event_name=event.name,
            vertical_id=event.vertical_id,
            head_poc=head_summary,
            poc_members=poc_member_summaries,
            total_poc_count=(1 if head_summary else 0) + len(poc_member_summaries),
        )

    def add_event_member(self, event_id: UUID, data: EventMemberCreate, actor_id: UUID) -> EventMember:
        event = self.get_event_by_id(event_id)
        actor = self.db.get(User, actor_id)
        target_user = self.db.get(User, data.user_id)
        if not target_user:
            raise EntityNotFoundException("User", str(data.user_id))

        if actor:
            from app.services.authority_service import AuthorityService
            AuthorityService(self.db).validate_event_member_assignment_authority(actor, target_user, event)

        existing = self.db.scalar(
            select(EventMember).where(EventMember.event_id == event.id, EventMember.user_id == data.user_id)
        )
        if existing:
            existing.role_in_event = data.role_in_event
            existing.status = EventMemberStatus.ACTIVE
            existing.notes = data.notes
            member = existing
        else:
            member = EventMember(
                event_id=event.id,
                user_id=data.user_id,
                role_in_event=data.role_in_event,
                status=EventMemberStatus.ACTIVE,
                assigned_by_id=actor_id,
                notes=data.notes,
            )
            self.db.add(member)

        self.db.flush()
        self.audit.log(
            action="EVENT_MEMBER_ADD",
            resource_type="EVENT_MEMBER",
            resource_id=str(member.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"event_id": str(event.id), "user_id": str(data.user_id), "role": data.role_in_event.value},
        )
        return member

    def update_event_member(self, event_id: UUID, member_id: UUID, data: EventMemberUpdate, actor_id: UUID) -> EventMember:
        member = self.db.scalar(
            select(EventMember).where(EventMember.id == member_id, EventMember.event_id == event_id)
        )
        if not member:
            raise EntityNotFoundException(f"Event member with ID '{member_id}' not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(member, key, value)

        self.audit.log(
            action="EVENT_MEMBER_UPDATE",
            resource_type="EVENT_MEMBER",
            resource_id=str(member.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return member

    def list_event_members(self, event_id: UUID) -> List[EventMember]:
        event = self.get_event_by_id(event_id)
        return list(
            self.db.scalars(
                select(EventMember)
                .where(EventMember.event_id == event.id)
                .options(selectinload(EventMember.user))
            ).all()
        )

    def update_readiness_item(
        self,
        event_id: UUID,
        item_id: UUID,
        data: EventReadinessUpdate,
        actor_id: UUID,
    ) -> EventReadinessItem:
        item = self.db.scalar(
            select(EventReadinessItem).where(
                EventReadinessItem.id == item_id,
                EventReadinessItem.event_id == event_id,
            )
        )
        if not item:
            raise EntityNotFoundException(f"Readiness item with ID '{item_id}' not found for this event")

        old_status = item.status
        item.status = data.status
        if data.assigned_user_id is not None:
            if data.assigned_user_id:
                event = self.get_event_by_id(event_id)
                self._validate_user_in_vertical(data.assigned_user_id, event.vertical_id, "Readiness Assignee")
            item.assigned_user_id = data.assigned_user_id
        if data.deadline is not None:
            item.deadline = data.deadline
        if data.evidence_link is not None:
            item.evidence_link = data.evidence_link
        if data.remarks is not None:
            item.remarks = data.remarks

        if data.status == ReadinessStatus.COMPLETED:
            item.completed_at = datetime.now(timezone.utc)
            item.completed_by_id = actor_id
        elif old_status == ReadinessStatus.COMPLETED and data.status != ReadinessStatus.COMPLETED:
            item.completed_at = None
            item.completed_by_id = None

        self.audit.log(
            action="EVENT_READINESS_UPDATE",
            resource_type="EVENT_READINESS_ITEM",
            resource_id=str(item.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"event_id": str(event_id), "category": item.category.value, "status": item.status.value},
        )
        return item

    def list_readiness_items(self, event_id: UUID, current_user: Optional[User] = None) -> List[EventReadinessItem]:
        self._validate_event_access(event_id, current_user)
        event = self.get_event_by_id(event_id, current_user=current_user)
        return list(
            self.db.scalars(
                select(EventReadinessItem)
                .where(EventReadinessItem.event_id == event.id)
                .options(
                    selectinload(EventReadinessItem.assigned_user),
                    selectinload(EventReadinessItem.completed_by),
                )
                .order_by(EventReadinessItem.category, EventReadinessItem.created_at)
            ).all()
        )

    def get_event_dashboard(self, event_id: UUID, current_user: Optional[User] = None) -> Dict[str, Any]:
        """
        Aggregates Event, Team, Tasks, Requirements, Meetings, Issues, and Readiness summary.
        Applies information boundary filtering: Event Team users cannot view confidential/sensitive issues.
        """
        self._validate_event_access(event_id, current_user)
        event = self.get_event_by_id(event_id, current_user=current_user)
        members = self.list_event_members(event_id)
        readiness = self.list_readiness_items(event_id, current_user=current_user)

        # Determine caller role for boundary enforcement
        is_event_team = False
        if current_user:
            roles = [
                r.name
                for r in self.db.scalars(
                    select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == current_user.id)
                ).all()
            ]
            is_event_team = "EVENT_TEAM" in roles and "ADMIN" not in roles and "SPORTS_CORE" not in roles

        # Summary of readiness
        readiness_summary = {
            "TOTAL": len(readiness),
            "COMPLETED": sum(1 for r in readiness if r.status == ReadinessStatus.COMPLETED),
            "IN_PROGRESS": sum(1 for r in readiness if r.status == ReadinessStatus.IN_PROGRESS),
            "NOT_STARTED": sum(1 for r in readiness if r.status == ReadinessStatus.NOT_STARTED),
            "BLOCKED": sum(1 for r in readiness if r.status == ReadinessStatus.BLOCKED),
        }

        # Query related tasks
        tasks = list(self.db.scalars(
            select(Task).where(Task.event_id == event_id).order_by(Task.deadline.asc()).limit(20)
        ).all())

        # Query related meetings
        meetings = list(self.db.scalars(
            select(Meeting).where(Meeting.event_id == event_id).order_by(Meeting.meeting_date.desc()).limit(20)
        ).all())

        # Query vertical-scoped requirements & issues
        requirements = list(self.db.scalars(
            select(Requirement).where(Requirement.requesting_vertical_id == event.vertical_id).order_by(Requirement.created_at.desc()).limit(20)
        ).all())

        # Boundary enforcement: Event Teams ONLY see NORMAL issues, never SENSITIVE or CONFIDENTIAL
        issue_stmt = select(Issue).where(Issue.vertical_id == event.vertical_id).order_by(Issue.created_at.desc())
        if is_event_team:
            issue_stmt = issue_stmt.where(Issue.sensitivity == IssueSensitivity.NORMAL)
        issues = list(self.db.scalars(issue_stmt.limit(20)).all())

        return {
            "event": event,
            "team_members": members,
            "readiness_items": readiness,
            "readiness_summary": readiness_summary,
            "tasks_count": len(tasks),
            "tasks": [{"id": str(t.id), "title": t.title, "status": t.status.value, "health": t.health.value, "progress": t.completion_percentage} for t in tasks],
            "requirements_count": len(requirements),
            "requirements": [{"id": str(r.id), "title": r.title, "status": r.status.value, "priority": r.priority.value} for r in requirements],
            "meetings_count": len(meetings),
            "meetings": [{"id": str(m.id), "title": m.title, "date": str(m.meeting_date), "status": m.status.value} for m in meetings],
            "issues_count": len(issues),
            "issues": [{"id": str(i.id), "title": i.title, "status": i.status.value, "sensitivity": i.sensitivity.value} for i in issues],
        }
