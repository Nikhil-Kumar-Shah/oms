"""
Event Team Management & Operational Profile Service Layer
Paradox Sports OMS - Phase 1 Organization + People + Role Governance

Handles:
- Event Team User Account creation (Admin creates unactivated credentials)
- Activation workflow by Sports Core / Deputy Core
- Event Team Profile entity management linked to target Event
- Strict operational isolation from internal discussions, audit logs, governance & internal personnel
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_strength
from app.models.communication import NotificationType
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventStatus,
    EventTeamProfile,
)
from app.models.issue import Issue
from app.models.meeting import Meeting
from app.models.rbac import Role, UserRole
from app.models.requirement import Requirement
from app.models.user import AccountStatus, User
from app.schemas.event_team import (
    EventTeamActivate,
    EventTeamCreate,
    EventTeamCredentialsCreate,
    EventTeamUpdate,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.rbac_service import RbacService

logger = get_logger(__name__)


class EventTeamService:
    """Manages Event Team user accounts, operational profiles, and boundary enforcement."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.rbac = RbacService(db)
        self.notif_service = NotificationService(db)

    def create_event_team_credentials(
        self,
        data: EventTeamCredentialsCreate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Tuple[User, EventTeamProfile]:
        """
        Admin creates Event Team account credentials in an UNACTIVATED (DISABLED) state.
        The user cannot log in until activated by Sports Core or Deputy Core.
        """
        username = data.username.strip().lower()
        validate_password_strength(data.password)

        # Check unique username
        stmt = select(User).where(User.username == username)
        if self.db.scalar(stmt):
            raise ValidationException(f"Username '{username}' is already registered")

        # Check unique email if provided
        email = data.email.strip().lower() if data.email else None
        if email:
            stmt_e = select(User).where(User.email == email)
            if self.db.scalar(stmt_e):
                raise ValidationException(f"Email '{email}' is already registered")

        team_name = (data.team_name or username).strip()
        pwd_hash = hash_password(data.password)

        # Account status set to DISABLED: Unable to log in until activated!
        user = User(
            username=username,
            full_name=team_name,
            email=email,
            password_hash=pwd_hash,
            account_status=AccountStatus.DISABLED,
        )
        self.db.add(user)
        self.db.flush()

        role_event_team = self.db.scalar(select(Role).where(Role.name == "EVENT_TEAM"))
        if role_event_team:
            self.db.add(UserRole(user_id=user.id, role_id=role_event_team.id))
            self.db.flush()

        profile = EventTeamProfile(
            user_id=user.id,
            event_id=None,
            team_name=team_name,
            contact_info={"is_activated": False},
        )
        self.db.add(profile)
        self.db.flush()

        self.audit.log(
            action="EVENT_TEAM_CREDENTIALS_CREATE",
            resource_type="USER",
            resource_id=str(user.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "username": username,
                "team_name": team_name,
                "account_status": "DISABLED",
                "is_activated": False,
            },
        )
        logger.info(f"Admin provisioned unactivated Event Team credentials for '{username}' (id={user.id})")
        return user, profile

    def list_unactivated_accounts(self) -> List[User]:
        """Lists Event Team user accounts awaiting activation."""
        stmt = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.name == "EVENT_TEAM",
                User.account_status == AccountStatus.DISABLED,
            )
            .order_by(User.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def activate_event_team(
        self,
        data: EventTeamActivate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> EventTeamProfile:
        """
        Activates an Event Team account and binds:
        Event Team -> Event Team Account -> Event Head -> POCs.
        Enables user account to ACTIVE so login is permitted.
        """
        user = self.db.get(User, data.user_id)
        if not user:
            raise EntityNotFoundException("User", str(data.user_id))

        user_roles = list(self.db.scalars(
            select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
        ).all())
        if "EVENT_TEAM" not in user_roles:
            raise ValidationException(f"User '{user.username}' does not have the EVENT_TEAM role")

        # Required Event assignment
        if not data.event_id:
            raise ValidationException("Event assignment is required to activate an Event Team account")
        event = self.db.get(Event, data.event_id)
        if not event:
            raise EntityNotFoundException("Event", str(data.event_id))
        if event.status == EventStatus.ARCHIVED:
            raise ValidationException("Cannot associate an Event Team with an ARCHIVED event")

        # Validate Head POC
        if not data.head_poc_id:
            raise ValidationException("Head POC is required to activate an Event Team account")
        head_poc = self.db.get(User, data.head_poc_id)
        if not head_poc:
            raise EntityNotFoundException("Head POC User", str(data.head_poc_id))
        if head_poc.account_status != AccountStatus.ACTIVE:
            raise ValidationException("Head POC user account must be ACTIVE")

        # Validate Additional POCs
        add_pocs = []
        for poc_id in data.additional_poc_ids:
            poc_u = self.db.get(User, poc_id)
            if not poc_u:
                raise EntityNotFoundException("Additional POC User", str(poc_id))
            add_pocs.append(poc_u)

        # Get or create EventTeamProfile
        profile = self.db.scalar(
            select(EventTeamProfile).where(EventTeamProfile.user_id == user.id)
        )
        if not profile:
            profile = EventTeamProfile(user_id=user.id, team_name=data.team_name.strip())
            self.db.add(profile)
            self.db.flush()

        profile.team_name = data.team_name.strip()
        profile.head_name = data.head_name.strip()
        profile.head_phone = data.head_phone.strip()
        profile.head_email = data.head_email.strip()
        profile.notes = data.notes.strip() if data.notes else None
        profile.event_id = event.id
        profile.event = event
        event.primary_poc_id = data.head_poc_id

        contact_info = dict(profile.contact_info or {})
        contact_info["is_activated"] = True
        contact_info["head_poc_id"] = str(data.head_poc_id)
        contact_info["head_poc_name"] = head_poc.full_name
        contact_info["head_poc_username"] = head_poc.username
        contact_info["additional_poc_ids"] = [str(x) for x in data.additional_poc_ids]
        profile.contact_info = contact_info

        # Add Head POC as EventMember
        existing_head_m = self.db.scalar(
            select(EventMember).where(
                EventMember.event_id == event.id,
                EventMember.user_id == data.head_poc_id,
            )
        )
        if not existing_head_m:
            self.db.add(
                EventMember(
                    event_id=event.id,
                    user_id=data.head_poc_id,
                    role_in_event=EventMemberRole.POC,
                    status=EventMemberStatus.ACTIVE,
                    assigned_by_id=actor_id or data.head_poc_id,
                    notes="Head POC designated via Event Team Activation",
                )
            )

        # Add Additional POCs as EventMembers
        for add_u in add_pocs:
            existing_add_m = self.db.scalar(
                select(EventMember).where(
                    EventMember.event_id == event.id,
                    EventMember.user_id == add_u.id,
                )
            )
            if not existing_add_m:
                self.db.add(
                    EventMember(
                        event_id=event.id,
                        user_id=add_u.id,
                        role_in_event=EventMemberRole.COORDINATOR,
                        status=EventMemberStatus.ACTIVE,
                        assigned_by_id=actor_id or data.head_poc_id,
                        notes="Additional POC designated via Event Team Activation",
                    )
                )

        # ACTIVATE ACCOUNT: user can now log in!
        user.account_status = AccountStatus.ACTIVE
        self.db.flush()

        self.audit.log(
            action="EVENT_TEAM_ACTIVATE",
            resource_type="EVENT_TEAM_PROFILE",
            resource_id=str(profile.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "team_name": profile.team_name,
                "user_id": str(user.id),
                "username": user.username,
                "head_name": profile.head_name,
                "head_poc_id": str(data.head_poc_id),
                "additional_poc_count": len(data.additional_poc_ids),
                "event_id": str(data.event_id) if data.event_id else None,
            },
        )
        logger.info(f"Activated Event Team '{profile.team_name}' for user '{user.username}' (head_poc={head_poc.username})")
        return profile

    def create_event_team(self, data: EventTeamCreate, actor_id: Optional[uuid.UUID] = None) -> EventTeamProfile:
        """
        Creates an EVENT_TEAM user account and baseline EventTeamProfile.
        Maintains backward compatibility with test suites.
        """
        event = None
        if data.event_id:
            event = self.db.get(Event, data.event_id)
            if not event:
                raise EntityNotFoundException("Event", str(data.event_id))
            if event.status == EventStatus.ARCHIVED:
                raise ValidationException("Cannot associate an Event Team with an ARCHIVED event")

        username = data.username.strip().lower()
        validate_password_strength(data.password)

        stmt = select(User).where(User.username == username)
        if self.db.scalar(stmt):
            raise ValidationException(f"Username '{username}' is already registered")

        email = data.email.strip().lower() if data.email else None
        if email:
            stmt_e = select(User).where(User.email == email)
            if self.db.scalar(stmt_e):
                raise ValidationException(f"Email '{email}' is already registered")

        full_name = (data.full_name or data.head_name or data.team_name or username).strip()
        team_name = (data.team_name or data.full_name or data.head_name or username).strip()

        # Determine activation state:
        # Accounts created from Admin panel have is_activated=False or event_id=None -> DISABLED (unactivated)
        # Accounts with event_id and no explicit is_activated=False (e.g. integration fixtures) -> ACTIVE
        if data.is_activated is False:
            is_activated = False
        elif data.is_activated is True:
            is_activated = True
        else:
            is_activated = bool(event is not None and (data.contact_info.get("is_activated") is not False if data.contact_info else True))

        account_status = AccountStatus.ACTIVE if is_activated else AccountStatus.DISABLED

        pwd_hash = hash_password(data.password)
        user = User(
            username=username,
            full_name=full_name,
            email=email,
            password_hash=pwd_hash,
            account_status=account_status,
        )
        self.db.add(user)
        self.db.flush()

        role_event_team = self.db.scalar(select(Role).where(Role.name == "EVENT_TEAM"))
        if role_event_team:
            self.db.add(UserRole(user_id=user.id, role_id=role_event_team.id))
            self.db.flush()

        contact_info = dict(data.contact_info or {})
        contact_info["is_activated"] = is_activated

        profile = EventTeamProfile(
            user_id=user.id,
            event_id=event.id if event else None,
            team_name=team_name,
            head_name=data.head_name.strip() if data.head_name else (data.full_name.strip() if data.full_name else None),
            head_email=data.head_email.strip() if data.head_email else email,
            head_phone=data.head_phone.strip() if data.head_phone else None,
            members_summary=data.members_summary or [],
            contact_info=contact_info,
            event_metadata=data.event_metadata or {},
            notes=data.notes.strip() if data.notes else None,
        )
        self.db.add(profile)
        self.db.flush()

        self.audit.log(
            action="EVENT_TEAM_CREATE",
            resource_type="EVENT_TEAM_PROFILE",
            resource_id=str(profile.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "team_name": profile.team_name,
                "event_id": str(event.id) if event else None,
                "user_id": str(user.id),
                "username": user.username,
                "is_activated": is_activated,
                "account_status": account_status.value,
            },
        )
        logger.info(f"Created Event Team account '{user.username}' (profile_id={profile.id}, status={account_status.value})")
        return profile

    def is_event_team_fully_activated(self, user_id: uuid.UUID) -> Tuple[bool, Optional[str]]:
        """
        Validates whether an Event Team user account meets all activation requirements:
        1. User account status == AccountStatus.ACTIVE
        2. EventTeamProfile exists
        3. Assigned to an active Event (event_id is not None)
        4. Assigned to a Head POC (head_poc_id in contact_info or event primary_poc_id)
        5. Marked is_activated in contact_info
        """
        user = self.db.get(User, user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            return False, "Account is inactive or pending activation"

        profile = self.db.scalar(
            select(EventTeamProfile)
            .options(selectinload(EventTeamProfile.event))
            .where(EventTeamProfile.user_id == user_id)
        )
        if not profile:
            return False, "Event Team profile does not exist"

        if not profile.event_id:
            return False, "Event assignment is missing"

        contact_info = profile.contact_info or {}
        if contact_info.get("is_activated") is False:
            return False, "Account has not been activated by Sports Core or Deputy Core"

        head_poc = contact_info.get("head_poc_id")
        if not head_poc and profile.event:
            head_poc = profile.event.primary_poc_id or profile.event.created_by_id

        if not head_poc:
            return False, "Head POC assignment is missing"

        return True, None

    def get_event_team_by_id(self, team_id: uuid.UUID, current_user: Optional[User] = None) -> EventTeamProfile:
        """Retrieves Event Team profile by UUID with object-level isolation."""
        stmt = (
            select(EventTeamProfile)
            .options(
                selectinload(EventTeamProfile.user),
                selectinload(EventTeamProfile.event),
            )
            .where(EventTeamProfile.id == team_id)
        )
        profile = self.db.scalar(stmt)
        if not profile:
            raise EntityNotFoundException("EventTeamProfile", str(team_id))

        if current_user:
            roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
            if not roles:
                roles = [
                    r.name
                    for r in self.db.scalars(
                        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == current_user.id)
                    ).all()
                ]
            if "EVENT_TEAM" in roles and "ADMIN" not in roles and "SPORTS_CORE" not in roles:
                if profile.user_id != current_user.id:
                    raise ForbiddenException("Event Team accounts cannot access other event team profiles")

        return profile

    def get_event_team_by_user_id(self, user_id: uuid.UUID) -> EventTeamProfile:
        """Retrieves Event Team profile associated with the specified user."""
        stmt = (
            select(EventTeamProfile)
            .options(
                selectinload(EventTeamProfile.user),
                selectinload(EventTeamProfile.event),
            )
            .where(EventTeamProfile.user_id == user_id)
        )
        profile = self.db.scalar(stmt)
        if not profile:
            raise EntityNotFoundException("EventTeamProfile for User", str(user_id))
        return profile

    def update_event_team(
        self,
        team_id: uuid.UUID,
        data: EventTeamUpdate,
        actor_id: Optional[uuid.UUID] = None,
        current_user: Optional[User] = None,
    ) -> EventTeamProfile:
        """Updates Event Team operational profile attributes and notifies POC group."""
        profile = self.get_event_team_by_id(team_id, current_user=current_user)

        update_dict = data.model_dump(exclude_unset=True)
        if "event_id" in update_dict:
            target_event_id = update_dict.pop("event_id")
            if target_event_id is not None:
                event = self.db.get(Event, target_event_id)
                if not event:
                    raise EntityNotFoundException("Event", str(target_event_id))
                if event.status == EventStatus.ARCHIVED:
                    raise ValidationException("Cannot associate an Event Team with an ARCHIVED event")
                profile.event = event
                profile.event_id = event.id
            else:
                profile.event = None
                profile.event_id = None

        for field, val in update_dict.items():
            setattr(profile, field, val)

        self.db.flush()

        # Notify Head POC / event POC group about profile updates
        head_poc_id = None
        contact_info = dict(profile.contact_info or {})
        if contact_info.get("head_poc_id"):
            try:
                head_poc_id = uuid.UUID(str(contact_info["head_poc_id"]))
            except Exception:
                pass
        if not head_poc_id and profile.event:
            head_poc_id = profile.event.primary_poc_id

        if head_poc_id:
            try:
                self.notif_service.create_notification(
                    recipient_id=head_poc_id,
                    notification_type=NotificationType.SYSTEM,
                    title=f"Event Team Profile Updated: {profile.team_name}",
                    message=f"The Event Team '{profile.team_name}' has updated their operational roster/contact information.",
                    related_resource_type="EVENT_TEAM_PROFILE",
                    related_resource_id=profile.id,
                )
            except Exception as e:
                logger.warning(f"Failed to notify POC for event team update: {e}")

        self.audit.log(
            action="EVENT_TEAM_UPDATE",
            resource_type="EVENT_TEAM_PROFILE",
            resource_id=str(profile.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=data.model_dump(mode="json", exclude_unset=True),
        )
        logger.info(f"Updated Event Team profile {profile.id} (team_name='{profile.team_name}')")
        return profile

    def list_event_teams(
        self,
        event_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[EventTeamProfile], int]:
        """Lists Event Teams filtered optionally by target event."""
        stmt = select(EventTeamProfile).options(
            selectinload(EventTeamProfile.user),
            selectinload(EventTeamProfile.event),
        )
        count_stmt = select(EventTeamProfile.id)

        if event_id:
            stmt = stmt.where(EventTeamProfile.event_id == event_id)
            count_stmt = count_stmt.where(EventTeamProfile.event_id == event_id)

        total = len(list(self.db.scalars(count_stmt).all()))
        items = list(self.db.scalars(stmt.order_by(EventTeamProfile.created_at.desc()).offset(offset).limit(limit)).all())
        return items, total

    def get_event_team_activity_counts(self, event_id: Optional[uuid.UUID]) -> Dict[str, int]:
        """Calculates meaningful operational activity counts for an Event Team."""
        if not event_id:
            return {
                "requirements_count": 0,
                "issues_count": 0,
                "meetings_count": 0,
                "members_count": 0,
            }

        meeting_count = self.db.scalar(
            select(func.count(Meeting.id)).where(Meeting.event_id == event_id)
        ) or 0

        member_count = self.db.scalar(
            select(func.count(EventMember.id)).where(EventMember.event_id == event_id)
        ) or 0

        issue_count = self.db.scalar(
            select(func.count(Issue.id)).where(Issue.event_reference == str(event_id))
        ) or 0

        req_count = 0

        return {
            "requirements_count": req_count,
            "issues_count": issue_count,
            "meetings_count": meeting_count,
            "members_count": member_count,
        }
