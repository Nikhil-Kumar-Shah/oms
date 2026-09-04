"""
Workspace Service - Unified Operational Dashboard
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload
from app.models.communication import (
    AcknowledgementStatus,
    Directive,
    DirectiveAcknowledgement,
    DirectiveStatus,
)
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventStatus,
    EventTeamProfile,
)
from app.models.form import (
    Form,
    FormResponse,
    FormResponseStatus,
    FormReviewer,
)
from app.models.governance import (
    OwnershipTransfer,
    TransferStatus,
)
from app.models.issue import (
    Issue,
    IssueAssignee,
    IssueSensitivity,
    IssueStatus,
)
from app.models.meeting import (
    Meeting,
    MeetingParticipant,
    MeetingStatus,
    RSVPStatus,
)
from app.models.organization import UserVertical, Vertical
from app.models.task import (
    Task,
    TaskHealth,
    TaskPriority,
    TaskStatus,
)
from app.models.user import User
from app.services.authority_service import AuthorityService
from app.services.rbac_service import RbacService
from app.schemas.workspace import (
    MyWorkDirectiveItem,
    MyWorkEventDutyItem,
    MyWorkFormItem,
    MyWorkIssueItem,
    MyWorkMeetingItem,
    MyWorkPriorityItem,
    MyWorkReviewItem,
    MyWorkStats,
    MyWorkTaskItem,
    MyWorkUserContext,
    UnifiedMyWorkResponse,
)


class WorkspaceService:
    """
    Unified Workspace Aggregator.
    All data is strictly derived from the server-authenticated session.
    """

    @staticmethod
    def get_unified_my_work(db: Session, current_user: User) -> UnifiedMyWorkResponse:
        now = datetime.now(timezone.utc)
        today = date.today()
        auth_service = AuthorityService(db)
        rbac_service = RbacService(db)
        effective_perms: Set[str] = set(rbac_service.get_effective_permissions(current_user.id))

        # -------------------------------------------------------------
        # 0. User Roles, Hierarchy & Context Resolution
        # -------------------------------------------------------------
        role_names: Set[str] = auth_service.get_user_role_names(current_user.id)
        operational_level: Optional[int] = auth_service.get_user_operational_level(current_user.id)
        is_admin_user: bool = auth_service.is_admin(current_user.id)
        is_exec_user: bool = auth_service.is_executive(current_user.id)
        is_event_team_user: bool = auth_service.is_event_team(current_user.id)

        # Determine Primary Canonical Role
        if is_admin_user:
            primary_role = "ADMIN"
        elif "SPORTS_CORE" in role_names or "CORE" in role_names:
            primary_role = "SPORTS_CORE"
        elif "DEPUTY_CORE" in role_names:
            primary_role = "DEPUTY_CORE"
        elif "SUPER_COORDINATOR" in role_names:
            primary_role = "SUPER_COORDINATOR"
        elif "COORDINATOR" in role_names:
            primary_role = "COORDINATOR"
        elif is_event_team_user:
            primary_role = "EVENT_TEAM"
        else:
            primary_role = "VOLUNTEER"

        # User's Assigned Verticals
        user_vert_records = db.execute(
            select(Vertical, UserVertical)
            .join(UserVertical, UserVertical.vertical_id == Vertical.id)
            .where(UserVertical.user_id == current_user.id)
        ).all()
        vertical_names = [v.name for v, _ in user_vert_records]
        user_vert_ids = [v.id for v, _ in user_vert_records]

        # User's Responsibilities Calculation
        responsibilities: List[str] = []
        if is_admin_user:
            responsibilities.append("System Administration & Governance")
        if primary_role == "SPORTS_CORE":
            responsibilities.append("Organization-Wide Sports Core Supervision")
        elif primary_role == "DEPUTY_CORE":
            responsibilities.append("Operational Leadership & Vertical Oversight")

        for v, uv in user_vert_records:
            if uv.is_primary:
                responsibilities.append(f"Primary Vertical: {v.name}")
            else:
                responsibilities.append(f"Vertical: {v.name}")

        # Event Head or Primary POC Responsibilities
        managed_events = db.execute(
            select(Event).where(
                or_(
                    Event.event_head_id == current_user.id,
                    Event.primary_poc_id == current_user.id,
                ),
                Event.status.notin_([EventStatus.COMPLETED, EventStatus.CANCELLED]),
            )
        ).scalars().all()
        for me in managed_events:
            if me.event_head_id == current_user.id:
                responsibilities.append(f"Event Head • {me.name}")
            elif me.primary_poc_id == current_user.id:
                responsibilities.append(f"Primary POC • {me.name}")

        # Event Team Profile Check
        event_team_profile = db.execute(
            select(EventTeamProfile)
            .options(joinedload(EventTeamProfile.event))
            .where(EventTeamProfile.user_id == current_user.id)
        ).scalars().first()

        event_team_dict: Optional[dict] = None
        if event_team_profile:
            responsibilities.append(f"Team Profile: {event_team_profile.team_name}")
            event_team_dict = {
                "team_name": event_team_profile.team_name,
                "head_name": event_team_profile.head_name,
                "head_email": event_team_profile.head_email,
                "head_phone": event_team_profile.head_phone,
                "event_id": str(event_team_profile.event_id) if event_team_profile.event_id else None,
                "event_name": event_team_profile.event.name if event_team_profile.event else None,
                "members_count": len(event_team_profile.members_summary) if event_team_profile.members_summary else 0,
            }

        # -------------------------------------------------------------
        # 1. Fetch Tasks
        # -------------------------------------------------------------
        def _build_task_item(t: Task) -> MyWorkTaskItem:
            event_name = t.event.name if t.event else None
            return MyWorkTaskItem(
                id=t.id,
                title=t.title,
                description=t.description,
                vertical_id=t.vertical_id,
                vertical_name=t.vertical.name if t.vertical else None,
                task_type=t.task_type,
                priority=t.priority,
                status=t.status,
                health=t.health,
                progress_percentage=t.completion_percentage,
                deadline=t.deadline,
                blocker_reason=t.blockers,
                assigned_to_id=t.assigned_to_id,
                assigned_to_name=t.assigned_to.full_name if t.assigned_to else None,
                assigned_to_username=t.assigned_to.username if t.assigned_to else None,
                assigned_by_id=t.assigned_by_id,
                assigned_by_name=t.assigned_by.full_name if t.assigned_by else None,
                assigned_by_username=t.assigned_by.username if t.assigned_by else None,
                event_id=t.event_id,
                event_title=event_name,
                created_at=t.created_at,
            )

        task_load_options = [
            joinedload(Task.vertical),
            joinedload(Task.event),
            joinedload(Task.assigned_to),
            joinedload(Task.assigned_by),
        ]

        task_query = (
            select(Task)
            .options(*task_load_options)
            .where(
                or_(
                    Task.assigned_to_id == current_user.id,
                    and_(Task.assigned_to_id.is_(None), Task.assigned_by_id == current_user.id),
                ),
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
            .order_by(Task.deadline.asc().nullslast(), Task.priority.desc())
        )
        active_tasks = db.execute(task_query).scalars().all()

        task_items: List[MyWorkTaskItem] = []
        blocker_items: List[MyWorkTaskItem] = []
        overdue_items: List[MyWorkTaskItem] = []

        for t in active_tasks:
            item = _build_task_item(t)
            task_items.append(item)

            if t.status == TaskStatus.BLOCKED or t.health == TaskHealth.BLOCKED:
                blocker_items.append(item)

            if t.deadline and t.deadline < now:
                overdue_items.append(item)

        completed_query = (
            select(Task)
            .options(*task_load_options)
            .where(
                or_(
                    Task.assigned_to_id == current_user.id,
                    and_(Task.assigned_to_id.is_(None), Task.assigned_by_id == current_user.id),
                ),
                Task.status == TaskStatus.COMPLETED,
            )
            .order_by(Task.completed_on.desc().nullslast(), Task.updated_at.desc())
        )
        completed_records = db.execute(completed_query).scalars().all()
        completed_items: List[MyWorkTaskItem] = [_build_task_item(t) for t in completed_records]

        created_by_me_query = (
            select(Task)
            .options(*task_load_options)
            .where(Task.assigned_by_id == current_user.id)
            .order_by(Task.created_at.desc())
        )
        created_by_me_records = db.execute(created_by_me_query).scalars().all()
        created_by_me_items: List[MyWorkTaskItem] = [_build_task_item(t) for t in created_by_me_records]

        # -------------------------------------------------------------
        # 2. Directives (Decommissioned per user requirements)
        # -------------------------------------------------------------
        pending_directives: List[MyWorkDirectiveItem] = []

        # -------------------------------------------------------------
        # 3. Fetch Upcoming Meetings
        # -------------------------------------------------------------
        meeting_query = (
            select(Meeting, MeetingParticipant)
            .options(joinedload(Meeting.organizer))
            .outerjoin(
                MeetingParticipant,
                and_(
                    MeetingParticipant.meeting_id == Meeting.id,
                    MeetingParticipant.user_id == current_user.id,
                ),
            )
            .where(
                or_(
                    Meeting.organizer_id == current_user.id,
                    MeetingParticipant.user_id == current_user.id,
                ),
                Meeting.meeting_date >= today,
                Meeting.status.notin_([MeetingStatus.COMPLETED, MeetingStatus.CANCELLED]),
            )
            .order_by(Meeting.meeting_date.asc(), Meeting.start_time.asc().nullslast())
        )
        meeting_records = db.execute(meeting_query).all()

        meeting_items: List[MyWorkMeetingItem] = []
        seen_meeting_ids = set()

        for m, part in meeting_records:
            if m.id in seen_meeting_ids:
                continue
            seen_meeting_ids.add(m.id)

            rsvp = part.rsvp_status if part else (RSVPStatus.ACCEPTED if m.organizer_id == current_user.id else RSVPStatus.PENDING)
            meeting_items.append(
                MyWorkMeetingItem(
                    id=m.id,
                    title=m.title,
                    meeting_type=m.meeting_type,
                    meeting_date=m.meeting_date,
                    start_time=m.start_time,
                    end_time=m.end_time,
                    location=m.location,
                    meeting_url=m.meeting_url,
                    rsvp_status=rsvp,
                    organizer_name=m.organizer.full_name if m.organizer else None,
                )
            )

        # -------------------------------------------------------------
        # 4. Fetch Assigned Event Duties
        # -------------------------------------------------------------
        event_query = (
            select(Event, EventMember)
            .outerjoin(
                EventMember,
                and_(
                    EventMember.event_id == Event.id,
                    EventMember.user_id == current_user.id,
                    EventMember.status == EventMemberStatus.ACTIVE,
                ),
            )
            .where(
                or_(
                    Event.primary_poc_id == current_user.id,
                    Event.event_head_id == current_user.id,
                    EventMember.user_id == current_user.id,
                ),
                Event.status.notin_([EventStatus.COMPLETED, EventStatus.CANCELLED]),
            )
            .order_by(Event.planned_date.asc())
        )
        event_records = db.execute(event_query).all()

        event_duties: List[MyWorkEventDutyItem] = []
        seen_event_ids = set()

        for ev, mem in event_records:
            if ev.id in seen_event_ids:
                continue
            seen_event_ids.add(ev.id)

            if ev.primary_poc_id == current_user.id:
                role = EventMemberRole.POC
            elif ev.event_head_id == current_user.id:
                role = EventMemberRole.HEAD
            elif mem:
                role = getattr(mem, "role_in_event", getattr(mem, "role", EventMemberRole.MEMBER))
            else:
                role = EventMemberRole.MEMBER

            event_duties.append(
                MyWorkEventDutyItem(
                    event_id=ev.id,
                    title=ev.name,
                    event_type=ev.event_type,
                    event_status=ev.status,
                    planned_date=ev.planned_date,
                    role=role,
                    location=ev.location,
                )
            )

        # -------------------------------------------------------------
        # 5. Fetch Pending Forms Assigned to User (Awaiting Response)
        # -------------------------------------------------------------
        pending_forms: List[MyWorkFormItem] = []
        can_access_forms = is_admin_user or "forms.submit" in effective_perms or "forms.read" in effective_perms
        if can_access_forms:
            pending_forms_query = (
                select(FormResponse)
                .options(joinedload(FormResponse.form).joinedload(Form.vertical))
                .where(
                    FormResponse.recipient_id == current_user.id,
                    FormResponse.status.in_([
                        FormResponseStatus.ASSIGNED,
                        FormResponseStatus.IN_PROGRESS,
                        FormResponseStatus.RETURNED,
                    ]),
                )
                .order_by(FormResponse.deadline.asc().nullslast(), FormResponse.created_at.desc())
            )
            form_response_records = db.execute(pending_forms_query).scalars().all()
            for fr in form_response_records:
                form_obj = fr.form
                if not form_obj:
                    continue
                deadline = fr.deadline
                if not deadline and form_obj.distribution_config:
                    raw_dl = form_obj.distribution_config.get("deadline")
                    if raw_dl:
                        try:
                            deadline = datetime.fromisoformat(raw_dl.replace("Z", "+00:00"))
                        except Exception:
                            pass

                instructions = form_obj.instructions
                if form_obj.distribution_config and form_obj.distribution_config.get("instructions"):
                    instructions = form_obj.distribution_config.get("instructions")

                pending_forms.append(
                    MyWorkFormItem(
                        id=fr.id,
                        form_id=form_obj.id,
                        form_title=form_obj.name,
                        purpose=form_obj.purpose,
                        category=form_obj.category or "Operational",
                        status=fr.status.value if hasattr(fr.status, "value") else str(fr.status),
                        deadline=deadline,
                        vertical_name=form_obj.vertical.name if form_obj.vertical else None,
                        instructions=instructions,
                        created_at=fr.created_at,
                    )
                )

        # -------------------------------------------------------------
        # 6. Fetch Pending Reviews & Approvals (Forms & Transfers)
        # -------------------------------------------------------------
        pending_reviews: List[MyWorkReviewItem] = []
        transfer_records = []

        # 6a. Form Reviews - ONLY if user has forms.review permission or is admin
        can_review_forms = is_admin_user or "forms.review" in effective_perms
        if can_review_forms:
            review_subquery = (
                select(FormReviewer.response_id)
                .where(FormReviewer.user_id == current_user.id, FormReviewer.status == "PENDING")
            )
            form_reviews_query = (
                select(FormResponse)
                .options(
                    joinedload(FormResponse.form),
                    joinedload(FormResponse.recipient),
                )
                .where(
                    or_(
                        FormResponse.current_reviewer_id == current_user.id,
                        FormResponse.id.in_(review_subquery),
                    ),
                    FormResponse.status.in_([
                        FormResponseStatus.SUBMITTED,
                        FormResponseStatus.RESUBMITTED,
                        FormResponseStatus.UNDER_REVIEW,
                    ]),
                )
                .order_by(FormResponse.submitted_at.desc().nullslast())
            )
            form_review_records = db.execute(form_reviews_query).scalars().all()
            for fr in form_review_records:
                if not fr.form:
                    continue
                pending_reviews.append(
                    MyWorkReviewItem(
                        id=fr.id,
                        item_type="FORM_REVIEW",
                        title=f"Form Review: {fr.form.name}",
                        submitted_by_name=fr.recipient.full_name if fr.recipient else (fr.recipient.username if fr.recipient else None),
                        submitted_at=fr.submitted_at or fr.resubmitted_at,
                        status=fr.status.value if hasattr(fr.status, "value") else str(fr.status),
                        urgency="HIGH" if fr.status == FormResponseStatus.RESUBMITTED else "NORMAL",
                        target_entity_id=fr.form_id,
                        link=f"/forms/{fr.form_id}",
                    )
                )

        # 6b. Resource Transfers (Governance Decommissioned per user requirements)
        transfer_records = []

        # -------------------------------------------------------------
        # 7. Fetch Active Issues Requiring Attention
        # -------------------------------------------------------------
        active_issues: List[MyWorkIssueItem] = []
        can_read_issues = is_admin_user or "issues.read" in effective_perms
        can_read_confidential = is_admin_user or is_exec_user or "issues.confidential.read" in effective_perms

        if can_read_issues:
            issue_assignee_subquery = (
                select(IssueAssignee.issue_id).where(IssueAssignee.user_id == current_user.id)
            )

            issue_filter_conditions = [
                Issue.assigned_to_id == current_user.id,
                Issue.id.in_(issue_assignee_subquery),
            ]

            if is_exec_user or is_admin_user:
                # Executive and Admin oversee active escalations org-wide
                issue_filter_conditions.append(Issue.status == IssueStatus.ESCALATED)
            elif primary_role in ("COORDINATOR", "SUPER_COORDINATOR") and user_vert_ids:
                # Coordinators oversee active escalations strictly within their assigned vertical division
                issue_filter_conditions.append(
                    and_(
                        Issue.status == IssueStatus.ESCALATED,
                        Issue.vertical_id.in_(user_vert_ids),
                    )
                )
            elif is_event_team_user and event_team_profile and event_team_profile.event:
                # Event team sees issues referencing their assigned event
                event_name_ref = event_team_profile.event.name
                issue_filter_conditions.append(Issue.event_reference == event_name_ref)

            issues_query = (
                select(Issue)
                .options(
                    joinedload(Issue.vertical),
                    joinedload(Issue.raised_by),
                    joinedload(Issue.assigned_to),
                    joinedload(Issue.issue_assignees),
                )
                .where(
                    or_(*issue_filter_conditions),
                    Issue.status.notin_([IssueStatus.RESOLVED, IssueStatus.CLOSED, IssueStatus.CANCELLED]),
                )
                .order_by(
                    (Issue.status == IssueStatus.ESCALATED).desc(),
                    Issue.deadline.asc().nullslast(),
                    Issue.date_raised.desc(),
                )
            )
            issue_records = db.execute(issues_query).unique().scalars().all()
            seen_issue_ids = set()
            for iss in issue_records:
                if iss.id in seen_issue_ids:
                    continue

                # Sensitivity enforcement: Confidential issues require confidential permission unless raised by or assigned to current user
                is_assigned_to_me = (
                    iss.assigned_to_id == current_user.id
                    or iss.raised_by_id == current_user.id
                    or any(ia.user_id == current_user.id for ia in getattr(iss, "issue_assignees", []))
                )

                if iss.sensitivity == IssueSensitivity.CONFIDENTIAL and not can_read_confidential:
                    if not is_assigned_to_me:
                        continue

                # Vertical scope isolation for non-executives
                if not (is_exec_user or is_admin_user) and not is_assigned_to_me:
                    if iss.vertical_id and iss.vertical_id not in user_vert_ids:
                        continue

                seen_issue_ids.add(iss.id)
                active_issues.append(
                    MyWorkIssueItem(
                        id=iss.id,
                        title=iss.title,
                        status=iss.status.value if hasattr(iss.status, "value") else str(iss.status),
                        sensitivity=iss.sensitivity.value if hasattr(iss.sensitivity, "value") else str(iss.sensitivity),
                        vertical_name=iss.vertical.name if iss.vertical else None,
                        event_reference=iss.event_reference,
                        raised_by_name=iss.raised_by.full_name if iss.raised_by else (iss.raised_by.username if iss.raised_by else None),
                        assigned_to_name=iss.assigned_to.full_name if iss.assigned_to else (iss.assigned_to.username if iss.assigned_to else None),
                        deadline=iss.deadline,
                        escalation_target=iss.escalation_target,
                        action_required=iss.action_required,
                        created_at=iss.date_raised,
                    )
                )

        # -------------------------------------------------------------
        # 8. Assemble Unified Priority Action Queue
        # -------------------------------------------------------------
        priority_items: List[MyWorkPriorityItem] = []

        # 8a. Overdue tasks
        for ot in overdue_items:
            priority_items.append(
                MyWorkPriorityItem(
                    id=f"overdue-task-{ot.id}",
                    item_type="TASK",
                    title=ot.title,
                    urgency="OVERDUE",
                    urgency_label="Overdue Task",
                    due_date=ot.deadline,
                    detail=f"Deadline passed ({ot.deadline.strftime('%b %d, %Y') if ot.deadline else 'Overdue'})",
                    action_link=f"/tasks/{ot.id}?from=my-tasks",
                    action_label="Resolve Task",
                )
            )

        # 8b. Blocked tasks
        for bt in blocker_items:
            priority_items.append(
                MyWorkPriorityItem(
                    id=f"blocked-task-{bt.id}",
                    item_type="TASK",
                    title=bt.title,
                    urgency="CRITICAL",
                    urgency_label="Blocked Task",
                    due_date=bt.deadline,
                    detail=bt.blocker_reason or "Reported operational impediment",
                    action_link=f"/tasks/{bt.id}?from=my-tasks",
                    action_label="Unblock Task",
                )
            )

        # 8c. Escalated issues
        for ai in active_issues:
            if ai.status == "ESCALATED":
                priority_items.append(
                    MyWorkPriorityItem(
                        id=f"escalation-issue-{ai.id}",
                        item_type="ISSUE",
                        title=ai.title,
                        urgency="CRITICAL",
                        urgency_label="Active Escalation",
                        due_date=ai.deadline,
                        detail=ai.escalation_target or "Immediate intervention required",
                        action_link=f"/issues/{ai.id}",
                        action_label="Review & Resolve",
                    )
                )

        # 8d. Form Reviews (Only if user has pending form reviews)
        for pr in pending_reviews:
            priority_items.append(
                MyWorkPriorityItem(
                    id=f"review-{pr.id}",
                    item_type="REVIEW",
                    title=pr.title,
                    urgency="APPROVAL_NEEDED",
                    urgency_label="Form Review",
                    due_date=None,
                    detail=f"Submitted by {pr.submitted_by_name or 'Respondent'}",
                    action_link=pr.link,
                    action_label="Review Form",
                )
            )

        # 8e. Urgent Forms with deadlines
        for pf in pending_forms:
            is_form_overdue = pf.deadline and pf.deadline < now
            is_form_soon = pf.deadline and (pf.deadline - now) <= timedelta(days=2)
            if is_form_overdue or is_form_soon:
                priority_items.append(
                    MyWorkPriorityItem(
                        id=f"urgent-form-{pf.id}",
                        item_type="FORM",
                        title=pf.form_title,
                        urgency="OVERDUE" if is_form_overdue else "DEADLINE_SOON",
                        urgency_label="Overdue Form Response" if is_form_overdue else "Form Due Soon",
                        due_date=pf.deadline,
                        detail=pf.purpose or "Required form submission",
                        action_link=f"/forms/{pf.form_id}",
                        action_label="Complete Form",
                    )
                )

        # 8f. Critical Priority Tasks due within 48 hours (not already overdue)
        for at in task_items:
            if at.priority == TaskPriority.CRITICAL and at not in overdue_items and at not in blocker_items:
                priority_items.append(
                    MyWorkPriorityItem(
                        id=f"critical-task-{at.id}",
                        item_type="TASK",
                        title=at.title,
                        urgency="CRITICAL",
                        urgency_label="Critical Priority Task",
                        due_date=at.deadline,
                        detail=f"Vertical: {at.vertical_name or 'General'}",
                        action_link=f"/tasks/{at.id}?from=my-tasks",
                        action_label="Work Task",
                    )
                )

        # -------------------------------------------------------------
        # 9. Concise Attention Summary
        # -------------------------------------------------------------
        attention_parts = []
        if len(overdue_items) > 0:
            attention_parts.append(f"{len(overdue_items)} overdue task{'s' if len(overdue_items) > 1 else ''}")
        if len(blocker_items) > 0:
            attention_parts.append(f"{len(blocker_items)} blocked task{'s' if len(blocker_items) > 1 else ''}")

        escalations_count = sum(1 for i in active_issues if i.status == "ESCALATED")
        if escalations_count > 0:
            attention_parts.append(f"{escalations_count} active escalation{'s' if escalations_count > 1 else ''}")

        if len(pending_reviews) > 0:
            attention_parts.append(f"{len(pending_reviews)} form{'s' if len(pending_reviews) > 1 else ''} awaiting review")

        urgent_forms_count = sum(1 for f in pending_forms if f.deadline and f.deadline < now)
        if urgent_forms_count > 0:
            attention_parts.append(f"{urgent_forms_count} overdue form response{'s' if urgent_forms_count > 1 else ''}")
        elif len(pending_forms) > 0:
            attention_parts.append(f"{len(pending_forms)} pending form response{'s' if len(pending_forms) > 1 else ''}")

        if attention_parts:
            attention_summary = f"Attention Required: You have {', '.join(attention_parts)} requiring your action."
            requires_attention = True
        else:
            attention_summary = "All caught up! You have no overdue deadlines, escalations, or pending reviews right now."
            requires_attention = False

        user_context = MyWorkUserContext(
            primary_role=primary_role,
            operational_level=operational_level,
            responsibilities=responsibilities,
            verticals=vertical_names,
            event_team_profile=event_team_dict,
            attention_summary=attention_summary,
            requires_immediate_attention=requires_attention,
        )

        # -------------------------------------------------------------
        # 10. Aggregated Metric Counters
        # -------------------------------------------------------------
        stats = MyWorkStats(
            active_tasks=len(task_items),
            completed_tasks=len(completed_items),
            created_by_me_tasks=len(created_by_me_items),
            pending_directives=len(pending_directives),
            upcoming_meetings=len(meeting_items),
            event_duties=len(event_duties),
            blocked_tasks=len(blocker_items),
            overdue_tasks=len(overdue_items),
            active_issues=len(active_issues),
            pending_forms=len(pending_forms),
            pending_reviews=len(pending_reviews),
            pending_approvals=len(transfer_records),
        )

        return UnifiedMyWorkResponse(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            context=user_context,
            stats=stats,
            priority_queue=priority_items,
            tasks=task_items,
            completed_tasks=completed_items,
            created_by_me_tasks=created_by_me_items,
            pending_forms=pending_forms,
            pending_reviews=pending_reviews,
            active_issues=active_issues,
            pending_directives=pending_directives,
            meetings=meeting_items,
            event_duties=event_duties,
            blockers=blocker_items,
            overdue=overdue_items,
        )
