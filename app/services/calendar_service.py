"""
Master & Personal Calendar Service Layer
Paradox Sports OMS - Phase 10G Architecture
Provides:
- Strict separation of Master vs. Personal calendars
- Zero-duplicate real-time dynamic projection of tasks, meetings, and events
- Universal Audience resolution and server-side authorization enforcement
- Comprehensive validation and error handling
"""

import uuid
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.calendar import (
    ActivityCategory,
    CalendarAudience,
    CalendarEntry,
    CalendarEntryUser,
    CalendarPriority,
    CalendarStatus,
    DeadlineType,
    RecurrenceFrequency,
)
from app.models.event import Event, EventMember, EventStatus
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, MeetingType
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.calendar import CalendarCreate, CalendarResponse, CalendarUpdate
from app.schemas.organization import AudienceResolveRequest
from app.services.audit_service import AuditService
from app.services.audience_service import AudienceService
from app.services.authority_service import AuthorityService
from app.services.notification_service import NotificationService
from app.services.rbac_service import RbacService

logger = get_logger("app.services.calendar")


class CalendarService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.authority = AuthorityService(db)
        self.audience_service = AudienceService(db)
        self.rbac = RbacService(db)
        self.notif_service = NotificationService(db)

    def compute_dynamic_status(
        self,
        activity_date: Optional[date] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        stored_status: Optional[CalendarStatus] = None,
        is_user_completed: bool = False,
        entry: Optional[CalendarEntry] = None,
    ) -> CalendarStatus:
        """
        Computes dynamic lifecycle status:
          - If participant marked completed -> COMPLETED
          - Stored terminal/explicit status (CANCELLED, COMPLETED, RESCHEDULED, IN_PROGRESS) -> retained
          - Future date / before start time -> UPCOMING
          - Scheduled window (start_time <= now <= end_time) -> IN_PROGRESS
          - Past end time or past date -> COMPLETED
        """
        if entry is not None:
            activity_date = entry.activity_date
            start_time = entry.start_time
            end_time = entry.end_time
            stored_status = entry.status

        if is_user_completed:
            return CalendarStatus.COMPLETED
        if stored_status in (
            CalendarStatus.CANCELLED,
            CalendarStatus.COMPLETED,
            CalendarStatus.RESCHEDULED,
            CalendarStatus.IN_PROGRESS,
        ):
            return stored_status

        now = datetime.now()
        today = now.date()

        if activity_date is not None and activity_date > today:
            return CalendarStatus.UPCOMING
        elif activity_date is not None and activity_date < today:
            return CalendarStatus.COMPLETED

        # activity_date == today
        current_time = now.time()
        s_time = start_time or time.min
        e_time = end_time or time.max

        if current_time < s_time:
            return CalendarStatus.UPCOMING
        elif s_time <= current_time <= e_time:
            return CalendarStatus.IN_PROGRESS
        else:
            return CalendarStatus.COMPLETED

    def _format_entry_response(
        self, entry: CalendarEntry, current_user_id: Optional[uuid.UUID] = None
    ) -> CalendarResponse:
        """Helper to convert CalendarEntry SQLAlchemy model into CalendarResponse Pydantic schema."""
        target_uids = [eu.user_id for eu in entry.entry_users] if entry.entry_users else []
        is_personal = (
            entry.audience == CalendarAudience.SPECIFIC_USERS
            and len(target_uids) == 1
            and target_uids[0] == entry.created_by_id
        )

        is_user_completed = False
        user_completed_at = None
        if current_user_id and entry.entry_users:
            user_eu = next((eu for eu in entry.entry_users if eu.user_id == current_user_id), None)
            if user_eu and user_eu.is_completed:
                is_user_completed = True
                user_completed_at = user_eu.completed_at

        effective_status = self.compute_dynamic_status(
            activity_date=entry.activity_date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            stored_status=entry.status,
            is_user_completed=is_user_completed,
        )

        return CalendarResponse(
            id=entry.id,
            title=entry.title,
            description=entry.description,
            activity_date=entry.activity_date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            category=entry.category,
            priority=entry.priority,
            status=effective_status,
            deadline_type=entry.deadline_type,
            audience=entry.audience,
            vertical_id=entry.vertical_id,
            vertical_name=entry.vertical.name if entry.vertical else None,
            event_reference=entry.event_reference,
            resource_link=entry.resource_link,
            remarks=entry.remarks,
            recurrence=entry.recurrence,
            recurrence_end_date=entry.recurrence_end_date,
            entity_type=entry.entity_type or "CALENDAR_ENTRY",
            entity_id=entry.entity_id or entry.id,
            is_personal=is_personal,
            task_id=entry.task_id,
            event_id=entry.event_id,
            meeting_id=entry.meeting_id,
            requirement_id=entry.requirement_id,
            created_by_id=entry.created_by_id,
            created_by_username=entry.created_by.username if entry.created_by else None,
            target_user_ids=target_uids,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            original_date=entry.original_date,
            rescheduled_at=entry.rescheduled_at,
            is_user_completed=is_user_completed,
            user_completed_at=user_completed_at,
        )

    def create_entry(self, data: CalendarCreate, actor_id: uuid.UUID) -> CalendarEntry:
        """
        Creates a calendar entry.
        Supports both Personal activities (no vertical required, actor-only visibility)
        and Organizational activities with Universal Audience resolution.
        """
        actor = self.db.get(User, actor_id)
        if not actor:
            raise EntityNotFoundException("User", str(actor_id))

        target_user_ids: List[uuid.UUID] = []
        target_vertical_id = data.vertical_id
        audience = data.audience or CalendarAudience.ORGANIZATION

        if data.is_personal:
            # Personal activity: no vertical division required, audience scoped to current user
            audience = CalendarAudience.SPECIFIC_USERS
            target_user_ids = [actor_id]
            target_vertical_id = data.vertical_id  # optional, may be None
        else:
            # Organizational activity: strictly requires Master Calendar authorization (Core, Deputy Core, Admin)
            is_master_auth = self.authority.is_master_calendar_authorized(actor_id)
            has_perm = self.rbac.has_permission(actor_id, "calendar.create")
            if not (is_master_auth or has_perm):
                raise ForbiddenException("Only Core, Deputy Core, and Admin can create organizational calendar activities")

            # Universal Audience resolution if multi-target selection provided
            if data.all_users or data.vertical_ids or data.role_ids or data.user_ids:
                aud_req = AudienceResolveRequest(
                    all_users=data.all_users or False,
                    vertical_ids=data.vertical_ids or [],
                    role_ids=data.role_ids or [],
                    user_ids=data.user_ids or [],
                    usage="audience",
                )
                aud_res = self.audience_service.resolve_audience(aud_req, actor)

                if data.all_users:
                    audience = CalendarAudience.ORGANIZATION
                elif data.vertical_ids and not data.role_ids and not data.user_ids:
                    audience = CalendarAudience.VERTICAL
                    target_vertical_id = data.vertical_ids[0]
                else:
                    audience = CalendarAudience.SPECIFIC_USERS
                    target_user_ids = aud_res.user_ids

            elif data.audience == CalendarAudience.ORGANIZATION:
                if not is_master_auth:
                    raise ForbiddenException("Non-executive roles cannot create organization-wide calendar entries")
            elif data.audience == CalendarAudience.VERTICAL:
                if not target_vertical_id:
                    raise ValidationException("Vertical ID is required when calendar audience is 'VERTICAL'")
                if not self.authority.has_vertical_access(actor_id, target_vertical_id):
                    raise ForbiddenException("Cannot create calendar entry outside your assigned vertical division")

        # Validate vertical exists if specified
        if target_vertical_id:
            stmt_v = select(Vertical).where(Vertical.id == target_vertical_id)
            vert = self.db.scalar(stmt_v)
            if not vert or vert.status != VerticalStatus.ACTIVE:
                raise ValidationException("Specified vertical division does not exist or is inactive")

        # Validate linked entities if supplied
        if data.task_id and not self.db.get(Task, data.task_id):
            raise EntityNotFoundException("Task", str(data.task_id))
        if data.event_id and not self.db.get(Event, data.event_id):
            raise EntityNotFoundException("Event", str(data.event_id))
        if data.meeting_id and not self.db.get(Meeting, data.meeting_id):
            raise EntityNotFoundException("Meeting", str(data.meeting_id))

        entry = CalendarEntry(
            title=data.title.strip(),
            description=data.description,
            activity_date=data.activity_date,
            start_time=data.start_time,
            end_time=data.end_time,
            category=data.category,
            priority=data.priority,
            status=data.status,
            deadline_type=data.deadline_type,
            audience=audience,
            vertical_id=target_vertical_id,
            event_reference=data.event_reference,
            resource_link=data.resource_link,
            remarks=data.remarks,
            recurrence=data.recurrence,
            recurrence_end_date=data.recurrence_end_date,
            entity_type=data.entity_type or "CALENDAR_ENTRY",
            entity_id=data.entity_id,
            task_id=data.task_id,
            event_id=data.event_id,
            meeting_id=data.meeting_id,
            requirement_id=data.requirement_id,
            created_by_id=actor_id,
        )
        self.db.add(entry)
        self.db.flush()

        # Link target users in calendar_entry_users association table
        if target_user_ids:
            for uid in set(target_user_ids):
                self.db.add(CalendarEntryUser(calendar_entry_id=entry.id, user_id=uid))
            self.db.flush()

            if not data.is_personal:
                recipient_ids = [uid for uid in set(target_user_ids) if uid != actor_id]
                if recipient_ids:
                    try:
                        self.notif_service.create_batch_notifications(
                            recipient_ids=recipient_ids,
                            title=f"New Calendar Activity: {entry.title}",
                            message=f"You have been included in the calendar activity '{entry.title}' scheduled for {entry.activity_date}.",
                            related_resource_type="CALENDAR_ENTRY",
                            related_resource_id=entry.id,
                        )
                    except Exception as ex:
                        logger.warning(f"Failed to dispatch calendar notifications: {ex}")

        self.audit.log(
            action="CALENDAR_CREATE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "title": entry.title,
                "is_personal": data.is_personal,
                "activity_date": entry.activity_date.isoformat(),
                "audience": entry.audience.value,
            },
        )

        logger.info(f"Created CalendarEntry '{entry.title}' (id={entry.id}, is_personal={data.is_personal})")
        return entry

    def get_entry_by_id(self, entry_id: uuid.UUID, user: Optional[User] = None) -> CalendarEntry:
        """Retrieves calendar entry by UUID with object-level authorization."""
        stmt = (
            select(CalendarEntry)
            .where(CalendarEntry.id == entry_id)
            .options(
                selectinload(CalendarEntry.vertical),
                selectinload(CalendarEntry.created_by),
                selectinload(CalendarEntry.entry_users),
            )
        )
        entry = self.db.scalar(stmt)
        if not entry:
            raise EntityNotFoundException("CalendarEntry", str(entry_id))

        if user:
            is_exec = self.authority.is_executive_or_admin(user.id)
            is_creator = entry.created_by_id == user.id
            is_target_user = any(eu.user_id == user.id for eu in entry.entry_users)
            user_vert_ids = self.authority.get_user_vertical_ids(user.id)
            is_vert = entry.vertical_id in user_vert_ids if entry.vertical_id else False
            is_org = entry.audience in (CalendarAudience.ORGANIZATION, CalendarAudience.ALL)

            if not (is_exec or is_creator or is_target_user or is_org or is_vert):
                raise ForbiddenException("You do not have authorization to view this calendar activity")

        return entry

    def list_personal_calendar(
        self,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[ActivityCategory] = None,
        priority: Optional[CalendarPriority] = None,
        status: Optional[CalendarStatus] = None,
        vertical_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 500,
    ) -> Tuple[List[CalendarResponse], int]:
        """
        Dynamically synthesizes the Personal Calendar for the authenticated user:
        1. Manual CalendarEntry records targeted to or created by user
        2. Real-time projection of assigned or created tasks with deadlines
        3. Real-time projection of meetings where user is attendee, organizer, or vertical member
        4. Real-time projection of events where user is member or vertical member
        Zero duplicate records are created in the database.
        """
        user_vert_ids = self.authority.get_user_vertical_ids(user.id)
        all_items: List[CalendarResponse] = []

        # -------------------------------------------------------------
        # 1. Manual Calendar Entries
        # -------------------------------------------------------------
        ce_subq = select(CalendarEntryUser.calendar_entry_id).where(CalendarEntryUser.user_id == user.id)
        stmt_ce = (
            select(CalendarEntry)
            .options(
                selectinload(CalendarEntry.vertical),
                selectinload(CalendarEntry.created_by),
                selectinload(CalendarEntry.entry_users),
            )
            .where(
                or_(
                    CalendarEntry.created_by_id == user.id,
                    CalendarEntry.id.in_(ce_subq),
                    CalendarEntry.audience.in_([CalendarAudience.ORGANIZATION, CalendarAudience.ALL]),
                    CalendarEntry.vertical_id.in_(user_vert_ids),
                )
            )
        )

        if start_date:
            stmt_ce = stmt_ce.where(CalendarEntry.activity_date >= start_date)
        if end_date:
            stmt_ce = stmt_ce.where(CalendarEntry.activity_date <= end_date)
        if category:
            stmt_ce = stmt_ce.where(CalendarEntry.category == category)
        if priority:
            stmt_ce = stmt_ce.where(CalendarEntry.priority == priority)
        if status:
            stmt_ce = stmt_ce.where(CalendarEntry.status == status)
        if vertical_id:
            stmt_ce = stmt_ce.where(CalendarEntry.vertical_id == vertical_id)

        entries = list(self.db.scalars(stmt_ce).all())
        for e in entries:
            all_items.append(self._format_entry_response(e, current_user_id=user.id))

        # -------------------------------------------------------------
        # 2. Dynamic Task Projections (Real-time synchronization)
        # -------------------------------------------------------------
        if category is None or category in (ActivityCategory.REPORT_DEADLINE, ActivityCategory.ACTIVITY):
            stmt_tasks = (
                select(Task)
                .options(selectinload(Task.vertical))
                .where(
                    Task.deadline.is_not(None),
                    or_(Task.assigned_to_id == user.id, Task.assigned_by_id == user.id),
                )
            )

            if start_date:
                stmt_tasks = stmt_tasks.where(func.date(Task.deadline) >= start_date)
            if end_date:
                stmt_tasks = stmt_tasks.where(func.date(Task.deadline) <= end_date)
            if priority:
                stmt_tasks = stmt_tasks.where(Task.priority == TaskPriority(priority.value))
            if vertical_id:
                stmt_tasks = stmt_tasks.where(Task.vertical_id == vertical_id)

            tasks = list(self.db.scalars(stmt_tasks).all())
            for t in tasks:
                t_status = (
                    CalendarStatus.COMPLETED
                    if t.status == TaskStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if t.status == TaskStatus.CANCELLED
                        else (CalendarStatus.IN_PROGRESS if t.status == TaskStatus.IN_PROGRESS else CalendarStatus.PLANNED)
                    )
                )
                if status and t_status != status:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=t.id,
                        title=f"Task: {t.title}",
                        description=t.description,
                        activity_date=t.deadline.date(),
                        start_time=t.deadline.time(),
                        end_time=None,
                        category=ActivityCategory.REPORT_DEADLINE,
                        priority=CalendarPriority(t.priority.value),
                        status=t_status,
                        deadline_type=DeadlineType.HARD_DEADLINE,
                        audience=CalendarAudience.SPECIFIC_USERS,
                        vertical_id=t.vertical_id,
                        vertical_name=t.vertical.name if t.vertical else None,
                        entity_type="TASK",
                        entity_id=t.id,
                        is_personal=(t.assigned_to_id == user.id and t.assigned_by_id == user.id),
                        task_id=t.id,
                        created_by_id=t.assigned_by_id or user.id,
                        resource_link=f"/tasks/{t.id}?from=calendar",
                        created_at=t.created_at,
                        updated_at=t.updated_at,
                    )
                )

        # -------------------------------------------------------------
        # 3. Dynamic Meeting Projections
        # -------------------------------------------------------------
        if category is None or category in (ActivityCategory.MEETING, ActivityCategory.REVIEW_MEETING):
            m_part_subq = select(MeetingParticipant.meeting_id).where(MeetingParticipant.user_id == user.id)
            stmt_meetings = (
                select(Meeting)
                .options(selectinload(Meeting.vertical))
                .where(
                    or_(
                        Meeting.organizer_id == user.id,
                        Meeting.id.in_(m_part_subq),
                        Meeting.vertical_id.in_(user_vert_ids),
                    )
                )
            )

            if start_date:
                stmt_meetings = stmt_meetings.where(Meeting.meeting_date >= start_date)
            if end_date:
                stmt_meetings = stmt_meetings.where(Meeting.meeting_date <= end_date)
            if vertical_id:
                stmt_meetings = stmt_meetings.where(Meeting.vertical_id == vertical_id)

            meetings = list(self.db.scalars(stmt_meetings).all())
            for m in meetings:
                m_status = (
                    CalendarStatus.COMPLETED
                    if m.status == MeetingStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if m.status in (MeetingStatus.CANCELLED, MeetingStatus.REJECTED)
                        else CalendarStatus.PLANNED
                    )
                )
                if status and m_status != status:
                    continue

                m_priority = (
                    CalendarPriority.HIGH
                    if m.meeting_type == MeetingType.EMERGENCY
                    else CalendarPriority.MEDIUM
                )
                if priority and m_priority != priority:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=m.id,
                        title=f"Meeting: {m.title}",
                        description=m.description,
                        activity_date=m.meeting_date,
                        start_time=m.start_time,
                        end_time=m.end_time,
                        category=ActivityCategory.MEETING,
                        priority=m_priority,
                        status=m_status,
                        deadline_type=DeadlineType.INFORMATIONAL,
                        audience=CalendarAudience.SPECIFIC_USERS,
                        vertical_id=m.vertical_id,
                        vertical_name=m.vertical.name if m.vertical else None,
                        entity_type="MEETING",
                        entity_id=m.id,
                        is_personal=False,
                        meeting_id=m.id,
                        created_by_id=m.organizer_id,
                        resource_link="/meetings",
                        created_at=m.created_at,
                        updated_at=m.updated_at,
                    )
                )

        # -------------------------------------------------------------
        # 4. Dynamic Event Projections
        # -------------------------------------------------------------
        if category is None or category == ActivityCategory.EVENT:
            ev_member_subq = select(EventMember.event_id).where(EventMember.user_id == user.id)
            stmt_events = (
                select(Event)
                .options(selectinload(Event.vertical))
                .where(
                    or_(
                        Event.event_head_id == user.id,
                        Event.primary_poc_id == user.id,
                        Event.id.in_(ev_member_subq),
                        Event.vertical_id.in_(user_vert_ids),
                    )
                )
            )

            if start_date:
                stmt_events = stmt_events.where(Event.planned_date >= start_date)
            if end_date:
                stmt_events = stmt_events.where(Event.planned_date <= end_date)
            if vertical_id:
                stmt_events = stmt_events.where(Event.vertical_id == vertical_id)

            events = list(self.db.scalars(stmt_events).all())
            for ev in events:
                ev_status = (
                    CalendarStatus.COMPLETED
                    if ev.status == EventStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if ev.status == EventStatus.CANCELLED
                        else (CalendarStatus.IN_PROGRESS if ev.status == EventStatus.IN_PROGRESS else CalendarStatus.PLANNED)
                    )
                )
                if status and ev_status != status:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=ev.id,
                        title=f"Event: {ev.name}",
                        description=ev.description,
                        activity_date=ev.planned_date,
                        start_time=ev.start_time,
                        end_time=ev.end_time,
                        category=ActivityCategory.EVENT,
                        priority=CalendarPriority.HIGH,
                        status=ev_status,
                        deadline_type=DeadlineType.INFORMATIONAL,
                        audience=CalendarAudience.ORGANIZATION,
                        vertical_id=ev.vertical_id,
                        vertical_name=ev.vertical.name if ev.vertical else None,
                        entity_type="EVENT",
                        entity_id=ev.id,
                        is_personal=False,
                        event_id=ev.id,
                        created_by_id=ev.created_by_id or user.id,
                        resource_link=f"/events/{ev.id}",
                        created_at=ev.created_at,
                        updated_at=ev.updated_at,
                    )
                )

        # Deduplicate and sort by date and start_time
        seen_ids = set()
        deduped: List[CalendarResponse] = []
        for item in all_items:
            key = (item.entity_type, item.entity_id or item.id)
            if key not in seen_ids:
                seen_ids.add(key)
                deduped.append(item)

        deduped.sort(key=lambda x: (x.activity_date, x.start_time or time.min))
        total = len(deduped)
        paged = deduped[skip : skip + limit]
        return paged, total

    def list_master_calendar(
        self,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[ActivityCategory] = None,
        priority: Optional[CalendarPriority] = None,
        status: Optional[CalendarStatus] = None,
        vertical_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 500,
    ) -> Tuple[List[CalendarResponse], int]:
        """
        Lists the organizational Master Calendar.
        Strictly requires calendar.read_master permission or executive role (ADMIN, SPORTS_CORE, DEPUTY_CORE).
        Unauthorized callers receive 403 Forbidden.
        """
        is_master_auth = self.authority.is_master_calendar_authorized(user.id)
        has_perm = self.rbac.has_permission(user.id, "calendar.read_master")
        if not (is_master_auth or has_perm):
            raise ForbiddenException("Only Core, Deputy Core, and Admin can access the Master Calendar")

        all_items: List[CalendarResponse] = []

        # -------------------------------------------------------------
        # 1. Organizational Calendar Entries
        # -------------------------------------------------------------
        stmt_ce = select(CalendarEntry).options(
            selectinload(CalendarEntry.vertical),
            selectinload(CalendarEntry.created_by),
            selectinload(CalendarEntry.entry_users),
        )

        is_exec = self.authority.is_executive_or_admin(user.id)
        if not is_exec:
            # Non-executives with calendar.read_master scoped to their verticals or org-wide entries
            user_vert_ids = self.authority.get_user_vertical_ids(user.id)
            stmt_ce = stmt_ce.where(
                or_(
                    CalendarEntry.audience.in_([CalendarAudience.ORGANIZATION, CalendarAudience.ALL]),
                    CalendarEntry.vertical_id.in_(user_vert_ids),
                    CalendarEntry.created_by_id == user.id,
                )
            )

        if start_date:
            stmt_ce = stmt_ce.where(CalendarEntry.activity_date >= start_date)
        if end_date:
            stmt_ce = stmt_ce.where(CalendarEntry.activity_date <= end_date)
        if category:
            stmt_ce = stmt_ce.where(CalendarEntry.category == category)
        if priority:
            stmt_ce = stmt_ce.where(CalendarEntry.priority == priority)
        if status:
            stmt_ce = stmt_ce.where(CalendarEntry.status == status)
        if vertical_id:
            stmt_ce = stmt_ce.where(CalendarEntry.vertical_id == vertical_id)

        entries = list(self.db.scalars(stmt_ce).all())
        for e in entries:
            # Exclude personal self-activities of other users
            resp = self._format_entry_response(e, current_user_id=user.id)
            if resp.is_personal and e.created_by_id != user.id:
                continue
            all_items.append(resp)

        # -------------------------------------------------------------
        # 2. Master Tasks Projection
        # -------------------------------------------------------------
        if category is None or category in (ActivityCategory.REPORT_DEADLINE, ActivityCategory.ACTIVITY):
            stmt_tasks = (
                select(Task)
                .options(selectinload(Task.vertical))
                .where(Task.deadline.is_not(None))
            )

            if not is_exec:
                user_vert_ids = self.authority.get_user_vertical_ids(user.id)
                stmt_tasks = stmt_tasks.where(Task.vertical_id.in_(user_vert_ids))

            if start_date:
                stmt_tasks = stmt_tasks.where(func.date(Task.deadline) >= start_date)
            if end_date:
                stmt_tasks = stmt_tasks.where(func.date(Task.deadline) <= end_date)
            if priority:
                stmt_tasks = stmt_tasks.where(Task.priority == TaskPriority(priority.value))
            if vertical_id:
                stmt_tasks = stmt_tasks.where(Task.vertical_id == vertical_id)

            tasks = list(self.db.scalars(stmt_tasks).all())
            for t in tasks:
                t_status = (
                    CalendarStatus.COMPLETED
                    if t.status == TaskStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if t.status == TaskStatus.CANCELLED
                        else (CalendarStatus.IN_PROGRESS if t.status == TaskStatus.IN_PROGRESS else CalendarStatus.PLANNED)
                    )
                )
                if status and t_status != status:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=t.id,
                        title=f"Task: {t.title}",
                        description=t.description,
                        activity_date=t.deadline.date(),
                        start_time=t.deadline.time(),
                        end_time=None,
                        category=ActivityCategory.REPORT_DEADLINE,
                        priority=CalendarPriority(t.priority.value),
                        status=t_status,
                        deadline_type=DeadlineType.HARD_DEADLINE,
                        audience=CalendarAudience.ORGANIZATION,
                        vertical_id=t.vertical_id,
                        vertical_name=t.vertical.name if t.vertical else None,
                        entity_type="TASK",
                        entity_id=t.id,
                        is_personal=False,
                        task_id=t.id,
                        created_by_id=t.assigned_by_id or user.id,
                        resource_link=f"/tasks/{t.id}?from=master-calendar",
                        created_at=t.created_at,
                        updated_at=t.updated_at,
                    )
                )

        # -------------------------------------------------------------
        # 3. Master Meetings Projection
        # -------------------------------------------------------------
        if category is None or category in (ActivityCategory.MEETING, ActivityCategory.REVIEW_MEETING):
            stmt_meetings = select(Meeting).options(selectinload(Meeting.vertical))
            if not is_exec:
                user_vert_ids = self.authority.get_user_vertical_ids(user.id)
                stmt_meetings = stmt_meetings.where(Meeting.vertical_id.in_(user_vert_ids))

            if start_date:
                stmt_meetings = stmt_meetings.where(Meeting.meeting_date >= start_date)
            if end_date:
                stmt_meetings = stmt_meetings.where(Meeting.meeting_date <= end_date)
            if vertical_id:
                stmt_meetings = stmt_meetings.where(Meeting.vertical_id == vertical_id)

            meetings = list(self.db.scalars(stmt_meetings).all())
            for m in meetings:
                m_status = (
                    CalendarStatus.COMPLETED
                    if m.status == MeetingStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if m.status in (MeetingStatus.CANCELLED, MeetingStatus.REJECTED)
                        else CalendarStatus.PLANNED
                    )
                )
                if status and m_status != status:
                    continue

                m_priority = (
                    CalendarPriority.HIGH
                    if m.meeting_type == MeetingType.EMERGENCY
                    else CalendarPriority.MEDIUM
                )
                if priority and m_priority != priority:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=m.id,
                        title=f"Meeting: {m.title}",
                        description=m.description,
                        activity_date=m.meeting_date,
                        start_time=m.start_time,
                        end_time=m.end_time,
                        category=ActivityCategory.MEETING,
                        priority=m_priority,
                        status=m_status,
                        deadline_type=DeadlineType.INFORMATIONAL,
                        audience=CalendarAudience.ORGANIZATION,
                        vertical_id=m.vertical_id,
                        vertical_name=m.vertical.name if m.vertical else None,
                        entity_type="MEETING",
                        entity_id=m.id,
                        is_personal=False,
                        meeting_id=m.id,
                        created_by_id=m.organizer_id,
                        resource_link="/meetings",
                        created_at=m.created_at,
                        updated_at=m.updated_at,
                    )
                )

        # -------------------------------------------------------------
        # 4. Master Events Projection
        # -------------------------------------------------------------
        if category is None or category == ActivityCategory.EVENT:
            stmt_events = select(Event).options(selectinload(Event.vertical))
            if not is_exec:
                user_vert_ids = self.authority.get_user_vertical_ids(user.id)
                stmt_events = stmt_events.where(Event.vertical_id.in_(user_vert_ids))

            if start_date:
                stmt_events = stmt_events.where(Event.planned_date >= start_date)
            if end_date:
                stmt_events = stmt_events.where(Event.planned_date <= end_date)
            if vertical_id:
                stmt_events = stmt_events.where(Event.vertical_id == vertical_id)

            events = list(self.db.scalars(stmt_events).all())
            for ev in events:
                ev_status = (
                    CalendarStatus.COMPLETED
                    if ev.status == EventStatus.COMPLETED
                    else (
                        CalendarStatus.CANCELLED
                        if ev.status == EventStatus.CANCELLED
                        else (CalendarStatus.IN_PROGRESS if ev.status == EventStatus.IN_PROGRESS else CalendarStatus.PLANNED)
                    )
                )
                if status and ev_status != status:
                    continue

                all_items.append(
                    CalendarResponse(
                        id=ev.id,
                        title=f"Event: {ev.name}",
                        description=ev.description,
                        activity_date=ev.planned_date,
                        start_time=ev.start_time,
                        end_time=ev.end_time,
                        category=ActivityCategory.EVENT,
                        priority=CalendarPriority.HIGH,
                        status=ev_status,
                        deadline_type=DeadlineType.INFORMATIONAL,
                        audience=CalendarAudience.ORGANIZATION,
                        vertical_id=ev.vertical_id,
                        vertical_name=ev.vertical.name if ev.vertical else None,
                        entity_type="EVENT",
                        entity_id=ev.id,
                        is_personal=False,
                        event_id=ev.id,
                        created_by_id=ev.created_by_id or user.id,
                        resource_link=f"/events/{ev.id}",
                        created_at=ev.created_at,
                        updated_at=ev.updated_at,
                    )
                )

        # Deduplicate and sort
        seen_ids = set()
        deduped: List[CalendarResponse] = []
        for item in all_items:
            key = (item.entity_type, item.entity_id or item.id)
            if key not in seen_ids:
                seen_ids.add(key)
                deduped.append(item)

        deduped.sort(key=lambda x: (x.activity_date, x.start_time or time.min))
        total = len(deduped)
        paged = deduped[skip : skip + limit]
        return paged, total

    def update_entry(self, entry_id: uuid.UUID, data: CalendarUpdate, actor_id: uuid.UUID) -> CalendarEntry:
        """Updates calendar entry attributes with authorization verification."""
        actor = self.db.get(User, actor_id)
        entry = self.get_entry_by_id(entry_id, user=actor)

        is_exec = self.authority.is_executive_or_admin(actor_id)
        has_perm = self.rbac.has_permission(actor_id, "calendar.update")
        if entry.created_by_id != actor_id and not (is_exec or has_perm):
            raise ForbiddenException("You do not have authorization to modify this calendar activity")

        if data.title is not None:
            entry.title = data.title.strip()
        if data.description is not None:
            entry.description = data.description
        if data.activity_date is not None:
            entry.activity_date = data.activity_date
        if data.start_time is not None:
            entry.start_time = data.start_time
        if data.end_time is not None:
            entry.end_time = data.end_time
        if data.category is not None:
            entry.category = data.category
        if data.priority is not None:
            entry.priority = data.priority
        if data.status is not None:
            entry.status = data.status
        if data.deadline_type is not None:
            entry.deadline_type = data.deadline_type
        if data.audience is not None:
            entry.audience = data.audience
        if data.vertical_id is not None:
            entry.vertical_id = data.vertical_id
        if data.event_reference is not None:
            entry.event_reference = data.event_reference
        if data.resource_link is not None:
            entry.resource_link = data.resource_link
        if data.remarks is not None:
            entry.remarks = data.remarks
        if data.recurrence is not None:
            entry.recurrence = data.recurrence
        if data.recurrence_end_date is not None:
            entry.recurrence_end_date = data.recurrence_end_date

        self.db.flush()

        self.audit.log(
            action="CALENDAR_UPDATE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"title": entry.title},
        )

        self.db.flush()
        return entry

    def delete_entry(self, entry_id: uuid.UUID, actor: User) -> None:
        """Deletes a calendar entry with authorization verification."""
        entry = self.get_entry_by_id(entry_id, user=actor)
        is_exec = self.authority.is_executive_or_admin(actor.id)
        has_perm = self.rbac.has_permission(actor.id, "calendar.update")

        if entry.created_by_id != actor.id and not (is_exec or has_perm):
            raise ForbiddenException("You do not have authorization to delete this calendar activity")

        self.db.delete(entry)
        self.db.flush()

        self.audit.log(
            action="CALENDAR_DELETE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry_id),
            outcome="SUCCESS",
            actor_id=actor.id,
            details={"title": entry.title},
        )

    def mark_individual_completion(self, entry_id: uuid.UUID, user: User) -> CalendarResponse:
        """
        Participant action: Marks the activity as completed for the current user only.
        Does NOT alter global CalendarEntry status for other participants.
        """
        entry = self.get_entry_by_id(entry_id, user=user)

        # Check or add to calendar_entry_users
        stmt = select(CalendarEntryUser).where(
            CalendarEntryUser.calendar_entry_id == entry.id,
            CalendarEntryUser.user_id == user.id,
        )
        eu = self.db.scalar(stmt)
        if not eu:
            eu = CalendarEntryUser(
                calendar_entry_id=entry.id,
                user_id=user.id,
                is_completed=True,
                completed_at=datetime.now(),
            )
            self.db.add(eu)
        else:
            eu.is_completed = True
            eu.completed_at = datetime.now()
        self.db.flush()

        self.audit.log(
            action="CALENDAR_PARTICIPANT_COMPLETE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=user.id,
            details={"title": entry.title, "user_id": str(user.id)},
        )

        return self._format_entry_response(entry, current_user_id=user.id)

    def complete_entry(
        self, entry_id: uuid.UUID, user: User, remarks: Optional[str] = None
    ) -> CalendarResponse:
        """
        Creator / authorized owner action: Marks activity as globally completed.
        Notifies all participants.
        """
        entry = self.get_entry_by_id(entry_id, user=user)
        is_creator = entry.created_by_id == user.id
        is_master_auth = self.authority.is_master_calendar_authorized(user.id)
        has_perm = self.rbac.has_permission(user.id, "calendar.update")

        if not (is_creator or is_master_auth or has_perm):
            raise ForbiddenException("You do not have authorization to globally complete this activity")

        entry.status = CalendarStatus.COMPLETED
        if remarks:
            entry.remarks = f"{entry.remarks}\n{remarks}".strip() if entry.remarks else remarks
        self.db.flush()

        # Notify attendees
        recipient_ids = [eu.user_id for eu in entry.entry_users if eu.user_id != user.id]
        if recipient_ids:
            try:
                self.notif_service.create_batch_notifications(
                    recipient_ids=recipient_ids,
                    title=f"Activity Completed: {entry.title}",
                    message=f"'{entry.title}' has been marked as completed by {user.username}.",
                    related_resource_type="CALENDAR_ENTRY",
                    related_resource_id=entry.id,
                )
            except Exception as ex:
                logger.warning(f"Failed to dispatch complete notification: {ex}")

        self.audit.log(
            action="CALENDAR_GLOBAL_COMPLETE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=user.id,
            details={"title": entry.title},
        )
        return self._format_entry_response(entry, current_user_id=user.id)

    def set_in_progress(
        self, entry_id: uuid.UUID, user: User, remarks: Optional[str] = None
    ) -> CalendarResponse:
        """
        Creator / authorized owner action: Sets activity to in-progress.
        """
        entry = self.get_entry_by_id(entry_id, user=user)
        is_creator = entry.created_by_id == user.id
        is_master_auth = self.authority.is_master_calendar_authorized(user.id)
        has_perm = self.rbac.has_permission(user.id, "calendar.update")

        if not (is_creator or is_master_auth or has_perm):
            raise ForbiddenException("You do not have authorization to modify this activity")

        entry.status = CalendarStatus.IN_PROGRESS
        if remarks:
            entry.remarks = f"{entry.remarks}\n{remarks}".strip() if entry.remarks else remarks
        self.db.flush()

        self.audit.log(
            action="CALENDAR_SET_IN_PROGRESS",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=user.id,
            details={"title": entry.title},
        )
        return self._format_entry_response(entry, current_user_id=user.id)

    def cancel_entry(
        self, entry_id: uuid.UUID, user: User, reason: Optional[str] = None
    ) -> CalendarResponse:
        """
        Creator / authorized owner action: Cancels activity and notifies participants.
        """
        entry = self.get_entry_by_id(entry_id, user=user)
        is_creator = entry.created_by_id == user.id
        is_master_auth = self.authority.is_master_calendar_authorized(user.id)
        has_perm = self.rbac.has_permission(user.id, "calendar.update")

        if not (is_creator or is_master_auth or has_perm):
            raise ForbiddenException("You do not have authorization to cancel this activity")

        entry.status = CalendarStatus.CANCELLED
        if reason:
            entry.remarks = f"Cancellation Reason: {reason}\n{entry.remarks or ''}".strip()
        self.db.flush()

        # Notify attendees
        recipient_ids = [eu.user_id for eu in entry.entry_users if eu.user_id != user.id]
        if recipient_ids:
            try:
                self.notif_service.create_batch_notifications(
                    recipient_ids=recipient_ids,
                    title=f"Activity Cancelled: {entry.title}",
                    message=f"'{entry.title}' scheduled for {entry.activity_date} has been cancelled"
                    + (f": {reason}" if reason else "."),
                    related_resource_type="CALENDAR_ENTRY",
                    related_resource_id=entry.id,
                )
            except Exception as ex:
                logger.warning(f"Failed to dispatch cancellation notification: {ex}")

        self.audit.log(
            action="CALENDAR_CANCEL",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=user.id,
            details={"title": entry.title, "reason": reason},
        )
        return self._format_entry_response(entry, current_user_id=user.id)

    def reschedule_entry(
        self,
        entry_id: uuid.UUID,
        user: User,
        new_date: date,
        new_start_time: Optional[time] = None,
        new_end_time: Optional[time] = None,
        reason: Optional[str] = None,
    ) -> CalendarResponse:
        """
        Creator / authorized owner action: Reschedules activity, records audit, and notifies participants.
        """
        entry = self.get_entry_by_id(entry_id, user=user)
        is_creator = entry.created_by_id == user.id
        is_master_auth = self.authority.is_master_calendar_authorized(user.id)
        has_perm = self.rbac.has_permission(user.id, "calendar.update")

        if not (is_creator or is_master_auth or has_perm):
            raise ForbiddenException("You do not have authorization to reschedule this activity")

        entry.original_date = entry.activity_date
        entry.rescheduled_at = datetime.now()
        entry.activity_date = new_date
        if new_start_time is not None:
            entry.start_time = new_start_time
        if new_end_time is not None:
            entry.end_time = new_end_time
        entry.status = CalendarStatus.RESCHEDULED
        if reason:
            entry.remarks = f"Reschedule Reason: {reason}\n{entry.remarks or ''}".strip()
        self.db.flush()

        # Notify attendees
        recipient_ids = [eu.user_id for eu in entry.entry_users if eu.user_id != user.id]
        if recipient_ids:
            try:
                self.notif_service.create_batch_notifications(
                    recipient_ids=recipient_ids,
                    title=f"Activity Rescheduled: {entry.title}",
                    message=f"'{entry.title}' has been moved to {new_date}"
                    + (f" ({reason})" if reason else "."),
                    related_resource_type="CALENDAR_ENTRY",
                    related_resource_id=entry.id,
                )
            except Exception as ex:
                logger.warning(f"Failed to dispatch reschedule notification: {ex}")

        self.audit.log(
            action="CALENDAR_RESCHEDULE",
            resource_type="CALENDAR_ENTRY",
            resource_id=str(entry.id),
            outcome="SUCCESS",
            actor_id=user.id,
            details={"title": entry.title, "new_date": new_date.isoformat(), "reason": reason},
        )
        return self._format_entry_response(entry, current_user_id=user.id)
