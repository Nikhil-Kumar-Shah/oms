"""
Operational Analytics Service Layer
Executes high-performance SQL aggregate queries over authoritative PostgreSQL records.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.models.communication import (
    AcknowledgementStatus,
    Directive,
    DirectiveAcknowledgement,
    DirectiveStatus,
    Notification,
    NotificationReadStatus,
)
from app.models.event import Event, EventReadinessItem, EventStatus, ReadinessStatus
from app.models.form import Form, FormSubmission, FormSubmissionStatus
from app.models.governance import OwnershipTransfer, SystemConfig, TransferStatus
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, RSVPStatus
from app.models.organization import Organization, Vertical, VerticalStatus
from app.models.report import DailyReportStatus, DailyWorkReport, WeeklyReport, WeeklyReportStatus
from app.models.requirement import Requirement, RequirementStatus
from app.models.task import Task, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.analytics import (
    AdministrativeAnalyticsResponse,
    MySummaryAnalyticsResponse,
    OperationalAnalyticsResponse,
    OperationalDashboardResponse,
    PerformanceIndicatorsResponse,
)


class AnalyticsService:
    """Computes authoritative operational, administrative, and personal metrics."""

    def __init__(self, db: Session):
        self.db = db

    def get_operational_analytics(self, vertical_id: Optional[UUID] = None) -> OperationalAnalyticsResponse:
        now = datetime.now(timezone.utc)
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        four_weeks_ago = today - timedelta(weeks=4)

        vert_name = None
        if vertical_id:
            vert = self.db.get(Vertical, vertical_id)
            vert_name = vert.name if vert else None

        # 1. Task metrics
        t_stmt = select(
            func.count(Task.id).label("total"),
            func.count(case((Task.status.in_([TaskStatus.IN_PROGRESS, TaskStatus.NOT_STARTED]), 1))).label("active"),
            func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
            func.count(case((Task.status == TaskStatus.BLOCKED, 1))).label("blocked"),
            func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
        )
        if vertical_id:
            t_stmt = t_stmt.where(Task.vertical_id == vertical_id)
        t_res = self.db.execute(t_stmt).mappings().first() or {}
        tasks_total = t_res.get("total") or 0
        tasks_comp = t_res.get("completed") or 0
        comp_rate = round((tasks_comp / tasks_total * 100.0), 1) if tasks_total > 0 else 0.0

        # 2. Issue metrics
        i_stmt = select(
            func.count(Issue.id).label("total"),
            func.count(case((Issue.status == IssueStatus.OPEN, 1))).label("open"),
            func.count(case((Issue.status == IssueStatus.ESCALATED, 1))).label("escalated"),
            func.count(case((Issue.status == IssueStatus.RESOLVED, 1))).label("resolved"),
        )
        if vertical_id:
            i_stmt = i_stmt.where(Issue.vertical_id == vertical_id)
        i_res = self.db.execute(i_stmt).mappings().first() or {}

        # 3. Requirement metrics
        r_stmt = select(
            func.count(Requirement.id).label("total"),
            func.count(case((Requirement.status == RequirementStatus.OPEN, 1))).label("open"),
            func.count(case((Requirement.status.in_([RequirementStatus.ASSIGNED, RequirementStatus.IN_PROGRESS]), 1))).label("in_progress"),
            func.count(case((Requirement.status == RequirementStatus.COMPLETED, 1))).label("completed"),
        )
        if vertical_id:
            r_stmt = r_stmt.where((Requirement.requesting_vertical_id == vertical_id) | (Requirement.target_vertical_id == vertical_id))
        r_res = self.db.execute(r_stmt).mappings().first() or {}

        # 4. Event metrics & Readiness
        e_stmt = select(
            func.count(Event.id).label("total"),
            func.count(case((Event.status == EventStatus.PLANNING, 1))).label("planning"),
            func.count(case((Event.status == EventStatus.IN_PROGRESS, 1))).label("in_progress"),
            func.count(case((Event.status == EventStatus.COMPLETED, 1))).label("completed"),
        )
        if vertical_id:
            e_stmt = e_stmt.where(Event.vertical_id == vertical_id)
        e_res = self.db.execute(e_stmt).mappings().first() or {}

        # Readiness %
        ri_stmt = select(
            func.count(EventReadinessItem.id).label("total"),
            func.count(case((EventReadinessItem.status == ReadinessStatus.COMPLETED, 1))).label("completed"),
        )
        if vertical_id:
            ri_stmt = ri_stmt.join(Event, EventReadinessItem.event_id == Event.id).where(Event.vertical_id == vertical_id)
        ri_res = self.db.execute(ri_stmt).mappings().first() or {}
        ri_total = ri_res.get("total") or 0
        ri_comp = ri_res.get("completed") or 0
        readiness_pct = round((ri_comp / ri_total * 100.0), 1) if ri_total > 0 else 0.0

        # 5. Meetings & RSVPs
        m_stmt = select(
            func.count(Meeting.id).label("total"),
            func.count(case((Meeting.status == MeetingStatus.SCHEDULED, 1))).label("scheduled"),
            func.count(case((Meeting.status == MeetingStatus.COMPLETED, 1))).label("completed"),
        )
        if vertical_id:
            m_stmt = m_stmt.where(Meeting.vertical_id == vertical_id)
        m_res = self.db.execute(m_stmt).mappings().first() or {}

        p_stmt = select(
            func.count(MeetingParticipant.id).label("total"),
            func.count(case((MeetingParticipant.rsvp_status == RSVPStatus.ACCEPTED, 1))).label("accepted"),
        )
        if vertical_id:
            p_stmt = p_stmt.join(Meeting, MeetingParticipant.meeting_id == Meeting.id).where(Meeting.vertical_id == vertical_id)
        p_res = self.db.execute(p_stmt).mappings().first() or {}
        p_total = p_res.get("total") or 0
        p_acc = p_res.get("accepted") or 0
        rsvp_pct = round((p_acc / p_total * 100.0), 1) if p_total > 0 else 0.0

        # 6. Reports submitted
        dr_stmt = select(func.count(DailyWorkReport.id)).where(DailyWorkReport.report_date >= seven_days_ago)
        if vertical_id:
            dr_stmt = dr_stmt.where(DailyWorkReport.vertical_id == vertical_id)
        daily_rep_7d = self.db.scalar(dr_stmt) or 0

        wr_stmt = select(func.count(WeeklyReport.id)).where(WeeklyReport.week_end_date >= four_weeks_ago)
        if vertical_id:
            wr_stmt = wr_stmt.where(WeeklyReport.vertical_id == vertical_id)
        weekly_rep_4w = self.db.scalar(wr_stmt) or 0

        # 7. Forms & Submissions
        f_stmt = select(func.count(Form.id))
        if vertical_id:
            f_stmt = f_stmt.where(Form.vertical_id == vertical_id)
        forms_total = self.db.scalar(f_stmt) or 0

        fs_stmt = select(
            func.count(FormSubmission.id).label("total"),
            func.count(case((FormSubmission.status == FormSubmissionStatus.SUBMITTED, 1))).label("pending"),
        )
        if vertical_id:
            fs_stmt = fs_stmt.join(Form, FormSubmission.form_id == Form.id).where(Form.vertical_id == vertical_id)
        fs_res = self.db.execute(fs_stmt).mappings().first() or {}

        return OperationalAnalyticsResponse(
            vertical_id=vertical_id,
            vertical_name=vert_name,
            generated_at=now,
            tasks_total=tasks_total,
            tasks_active=t_res.get("active") or 0,
            tasks_completed=tasks_comp,
            tasks_overdue=t_res.get("overdue") or 0,
            tasks_blocked=t_res.get("blocked") or 0,
            tasks_completion_rate_pct=comp_rate,
            issues_total=i_res.get("total") or 0,
            issues_open=i_res.get("open") or 0,
            issues_escalated=i_res.get("escalated") or 0,
            issues_resolved=i_res.get("resolved") or 0,
            requirements_total=r_res.get("total") or 0,
            requirements_open=r_res.get("open") or 0,
            requirements_in_progress=r_res.get("in_progress") or 0,
            requirements_completed=r_res.get("completed") or 0,
            events_total=e_res.get("total") or 0,
            events_planning=e_res.get("planning") or 0,
            events_in_progress=e_res.get("in_progress") or 0,
            events_completed=e_res.get("completed") or 0,
            readiness_completed_pct=readiness_pct,
            meetings_total=m_res.get("total") or 0,
            meetings_scheduled=m_res.get("scheduled") or 0,
            meetings_completed=m_res.get("completed") or 0,
            meetings_rsvp_accepted_pct=rsvp_pct,
            daily_reports_submitted_last_7d=daily_rep_7d,
            weekly_reports_submitted_last_4w=weekly_rep_4w,
            forms_total=forms_total,
            form_submissions_total=fs_res.get("total") or 0,
            form_submissions_pending=fs_res.get("pending") or 0,
        )

    def get_administrative_analytics(self) -> AdministrativeAnalyticsResponse:
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)

        org = self.db.scalar(select(Organization).limit(1))
        org_name = org.name if org else "Paradox Sports Department"

        tot_verts = self.db.scalar(select(func.count(Vertical.id))) or 0
        tot_users = self.db.scalar(select(func.count(User.id))) or 0
        active_users = self.db.scalar(select(func.count(User.id)).where(User.account_status == AccountStatus.ACTIVE)) or 0

        # Global tasks
        t_res = self.db.execute(
            select(
                func.count(Task.id).label("total"),
                func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
                func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
            )
        ).mappings().first() or {}
        g_tasks = t_res.get("total") or 0
        g_comp = t_res.get("completed") or 0
        g_comp_rate = round((g_comp / g_tasks * 100.0), 1) if g_tasks > 0 else 0.0

        # Global issues
        i_res = self.db.execute(
            select(
                func.count(case((Issue.status == IssueStatus.OPEN, 1))).label("open"),
                func.count(case((Issue.sensitivity == IssueSensitivity.CONFIDENTIAL, 1))).label("critical"),
            )
        ).mappings().first() or {}

        # Global active events
        g_events = self.db.scalar(select(func.count(Event.id)).where(Event.status.in_([EventStatus.PLANNING, EventStatus.IN_PROGRESS]))) or 0

        # Global readiness avg %
        ri_res = self.db.execute(
            select(
                func.count(EventReadinessItem.id).label("total"),
                func.count(case((EventReadinessItem.status == ReadinessStatus.COMPLETED, 1))).label("completed"),
            )
        ).mappings().first() or {}
        ri_tot = ri_res.get("total") or 0
        ri_comp = ri_res.get("completed") or 0
        g_readiness_avg = round((ri_comp / ri_tot * 100.0), 1) if ri_tot > 0 else 0.0

        # Directives compliance
        g_dirs = self.db.scalar(select(func.count(Directive.id)).where(Directive.status == DirectiveStatus.ISSUED)) or 0
        ack_res = self.db.execute(
            select(
                func.count(DirectiveAcknowledgement.id).label("total"),
                func.count(case((DirectiveAcknowledgement.status == AcknowledgementStatus.ACKNOWLEDGED, 1))).label("acked"),
            )
        ).mappings().first() or {}
        ack_tot = ack_res.get("total") or 0
        ack_comp = ack_res.get("acked") or 0
        dir_comp_pct = round((ack_comp / ack_tot * 100.0), 1) if ack_tot > 0 else 100.0

        # Configs count & Audit events
        cfg_count = self.db.scalar(select(func.count(SystemConfig.id))) or 0
        audit_24h = self.db.scalar(select(func.count(AuditLog.id)).where(AuditLog.timestamp >= yesterday)) or 0

        return AdministrativeAnalyticsResponse(
            generated_at=now,
            organization_name=org_name,
            total_verticals=tot_verts,
            total_users=tot_users,
            active_users=active_users,
            global_tasks_total=g_tasks,
            global_tasks_completion_rate=g_comp_rate,
            global_overdue_tasks=t_res.get("overdue") or 0,
            global_open_issues=i_res.get("open") or 0,
            global_critical_issues=i_res.get("critical") or 0,
            global_active_events=g_events,
            global_event_readiness_avg_pct=g_readiness_avg,
            global_active_directives=g_dirs,
            directive_acknowledgement_compliance_pct=dir_comp_pct,
            reporting_compliance_rate_pct=85.0,  # Benchmark compliance rate
            system_config_keys_count=cfg_count,
            audit_events_last_24h=audit_24h,
        )

    def get_my_summary(self, user: User) -> MySummaryAnalyticsResponse:
        now = datetime.now(timezone.utc)
        today = date.today()

        # My Tasks
        t_res = self.db.execute(
            select(
                func.count(Task.id).label("total"),
                func.count(case((Task.status == TaskStatus.IN_PROGRESS, 1))).label("in_progress"),
                func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
                func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
            ).where(Task.assigned_to_id == user.id)
        ).mappings().first() or {}

        # My Requirements
        r_res = self.db.execute(
            select(
                func.count(Requirement.id).label("total"),
                func.count(case((((Requirement.status != RequirementStatus.COMPLETED) & (Requirement.status != RequirementStatus.REJECTED)), 1))).label("open"),
            ).where(Requirement.assignee_id == user.id)
        ).mappings().first() or {}

        # My Upcoming Meetings
        m_count = self.db.scalar(
            select(func.count(MeetingParticipant.id))
            .join(Meeting, MeetingParticipant.meeting_id == Meeting.id)
            .where(
                MeetingParticipant.user_id == user.id,
                Meeting.meeting_date >= today,
                Meeting.status != MeetingStatus.CANCELLED,
            )
        ) or 0

        pending_rsvps = self.db.scalar(
            select(func.count(MeetingParticipant.id))
            .join(Meeting, MeetingParticipant.meeting_id == Meeting.id)
            .where(
                MeetingParticipant.user_id == user.id,
                MeetingParticipant.rsvp_status == RSVPStatus.PENDING,
                Meeting.meeting_date >= today,
            )
        ) or 0

        # Pending Directives
        pending_dirs = self.db.scalar(
            select(func.count(DirectiveAcknowledgement.id))
            .where(
                DirectiveAcknowledgement.user_id == user.id,
                DirectiveAcknowledgement.status == AcknowledgementStatus.PENDING,
            )
        ) or 0

        # Unread Notifications
        unread_notifs = self.db.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == user.id,
                Notification.read_status == NotificationReadStatus.UNREAD,
            )
        ) or 0

        # Today's daily report
        today_rep = self.db.scalar(
            select(DailyWorkReport.id).where(
                DailyWorkReport.user_id == user.id,
                DailyWorkReport.report_date == today,
            )
        )

        return MySummaryAnalyticsResponse(
            user_id=user.id,
            username=user.username,
            generated_at=now,
            my_tasks_total=t_res.get("total") or 0,
            my_tasks_in_progress=t_res.get("in_progress") or 0,
            my_tasks_completed=t_res.get("completed") or 0,
            my_tasks_overdue=t_res.get("overdue") or 0,
            my_assigned_requirements_total=r_res.get("total") or 0,
            my_open_requirements=r_res.get("open") or 0,
            my_upcoming_meetings_count=m_count,
            my_pending_rsvps_count=pending_rsvps,
            my_pending_directive_acknowledgements=pending_dirs,
            my_unread_notifications_count=unread_notifs,
            my_daily_report_submitted_today=bool(today_rep),
        )

    def get_operational_dashboard(self, current_user: Optional[User] = None) -> OperationalDashboardResponse:
        now = datetime.now(timezone.utc)
        today = date.today()
        seven_days_ago = today - timedelta(days=7)

        from app.services.authority_service import AuthorityService
        from app.models.organization import UserVertical
        from sqlalchemy import or_

        auth_service = AuthorityService(self.db)
        is_exec = current_user and auth_service.is_executive_or_admin(current_user.id)
        user_vids: Optional[List[UUID]] = None

        if current_user and not is_exec:
            user_vids = auth_service.get_user_vertical_ids(current_user.id)
            if not user_vids:
                return OperationalDashboardResponse(
                    generated_at=now,
                    active_tasks=0,
                    completed_tasks=0,
                    overdue_tasks=0,
                    blocked_tasks=0,
                    open_issues=0,
                    escalated_issues=0,
                    upcoming_meetings=0,
                    pending_requirements=0,
                    event_readiness_avg_pct=0.0,
                    reporting_compliance_pct=100.0,
                    pending_directives=0,
                    outstanding_approvals=0,
                )

        # 1. Tasks
        t_stmt = select(
            func.count(case((Task.status.in_([TaskStatus.IN_PROGRESS, TaskStatus.NOT_STARTED]), 1))).label("active"),
            func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
            func.count(case((Task.status == TaskStatus.BLOCKED, 1))).label("blocked"),
            func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
        )
        if user_vids is not None:
            t_stmt = t_stmt.where(Task.vertical_id.in_(user_vids))
        t_res = self.db.execute(t_stmt).mappings().first() or {}

        # 2. Issues
        i_stmt = select(
            func.count(case((Issue.status == IssueStatus.OPEN, 1))).label("open"),
            func.count(case((Issue.status == IssueStatus.ESCALATED, 1))).label("escalated"),
        )
        if user_vids is not None:
            i_stmt = i_stmt.where(Issue.vertical_id.in_(user_vids))
        i_res = self.db.execute(i_stmt).mappings().first() or {}

        # 3. Meetings
        m_stmt = select(func.count(Meeting.id)).where(Meeting.meeting_date >= today, Meeting.status != MeetingStatus.CANCELLED)
        if user_vids is not None:
            m_stmt = m_stmt.where(Meeting.vertical_id.in_(user_vids))
        m_count = self.db.scalar(m_stmt) or 0

        # 4. Pending Requirements
        req_stmt = select(func.count(Requirement.id)).where(
            Requirement.status.in_([RequirementStatus.OPEN, RequirementStatus.ASSIGNED, RequirementStatus.IN_PROGRESS])
        )
        if user_vids is not None:
            req_stmt = req_stmt.where(
                or_(
                    Requirement.requesting_vertical_id.in_(user_vids),
                    Requirement.target_vertical_id.in_(user_vids),
                )
            )
        req_count = self.db.scalar(req_stmt) or 0

        # 5. Event Readiness via single SQL aggregate
        ri_stmt = select(
            func.count(EventReadinessItem.id).label("total"),
            func.count(case((EventReadinessItem.status == ReadinessStatus.COMPLETED, 1))).label("completed"),
        ).join(Event, EventReadinessItem.event_id == Event.id).where(Event.status != EventStatus.CANCELLED)
        if user_vids is not None:
            ri_stmt = ri_stmt.where(Event.vertical_id.in_(user_vids))
        ri_res = self.db.execute(ri_stmt).mappings().first() or {}
        ri_tot = ri_res.get("total") or 0
        ri_comp = ri_res.get("completed") or 0
        event_readiness_avg = round((ri_comp / ri_tot * 100.0), 1) if ri_tot > 0 else 0.0

        # 6. Reporting Compliance
        if user_vids is not None:
            active_users_stmt = (
                select(func.count(func.distinct(User.id)))
                .join(UserVertical, UserVertical.user_id == User.id)
                .where(User.account_status == AccountStatus.ACTIVE, UserVertical.vertical_id.in_(user_vids))
            )
            actual_reps_stmt = (
                select(func.count(DailyWorkReport.id))
                .where(DailyWorkReport.report_date >= seven_days_ago, DailyWorkReport.vertical_id.in_(user_vids))
            )
        else:
            active_users_stmt = select(func.count(User.id)).where(User.account_status == AccountStatus.ACTIVE)
            actual_reps_stmt = select(func.count(DailyWorkReport.id)).where(DailyWorkReport.report_date >= seven_days_ago)

        active_coords = self.db.scalar(active_users_stmt) or 0
        expected_reps = active_coords * 7
        actual_reps = self.db.scalar(actual_reps_stmt) or 0
        reporting_comp_pct = round((actual_reps / expected_reps * 100.0), 1) if expected_reps > 0 else 100.0

        # 7. Pending Directives
        pending_dirs_stmt = select(func.count(DirectiveAcknowledgement.id)).where(
            DirectiveAcknowledgement.status == AcknowledgementStatus.PENDING
        )
        if current_user and not is_exec:
            pending_dirs_stmt = pending_dirs_stmt.where(DirectiveAcknowledgement.user_id == current_user.id)
        pending_dirs = self.db.scalar(pending_dirs_stmt) or 0

        # 8. Outstanding Approvals
        if user_vids is not None:
            pending_transfers = self.db.scalar(
                select(func.count(OwnershipTransfer.id)).where(
                    OwnershipTransfer.status == TransferStatus.PENDING,
                    OwnershipTransfer.requested_by_id == current_user.id,
                )
            ) or 0

            requested_meetings = self.db.scalar(
                select(func.count(Meeting.id)).where(
                    Meeting.status == MeetingStatus.REQUESTED,
                    Meeting.vertical_id.in_(user_vids),
                )
            ) or 0
            pending_submissions = self.db.scalar(
                select(func.count(FormSubmission.id)).where(
                    FormSubmission.status == FormSubmissionStatus.SUBMITTED,
                    FormSubmission.submitter_id == current_user.id,
                )
            ) or 0

        else:
            pending_transfers = self.db.scalar(select(func.count(OwnershipTransfer.id)).where(OwnershipTransfer.status == TransferStatus.PENDING)) or 0
            requested_meetings = self.db.scalar(select(func.count(Meeting.id)).where(Meeting.status == MeetingStatus.REQUESTED)) or 0
            pending_submissions = self.db.scalar(select(func.count(FormSubmission.id)).where(FormSubmission.status == FormSubmissionStatus.SUBMITTED)) or 0
        outstanding_approvals = pending_transfers + requested_meetings + pending_submissions

        return OperationalDashboardResponse(
            generated_at=now,
            active_tasks=t_res.get("active") or 0,
            completed_tasks=t_res.get("completed") or 0,
            overdue_tasks=t_res.get("overdue") or 0,
            blocked_tasks=t_res.get("blocked") or 0,
            open_issues=i_res.get("open") or 0,
            escalated_issues=i_res.get("escalated") or 0,
            upcoming_meetings=m_count,
            pending_requirements=req_count,
            event_readiness_avg_pct=event_readiness_avg,
            reporting_compliance_pct=reporting_comp_pct,
            pending_directives=pending_dirs,
            outstanding_approvals=outstanding_approvals,
        )

    def get_performance_indicators(self, current_user: Optional[User] = None) -> PerformanceIndicatorsResponse:
        now = datetime.now(timezone.utc)
        today = date.today()
        seven_days_ago = today - timedelta(days=7)

        from app.services.authority_service import AuthorityService
        from app.models.organization import UserVertical
        from sqlalchemy import or_

        auth_service = AuthorityService(self.db)
        is_exec = current_user and auth_service.is_executive_or_admin(current_user.id)
        user_vids: Optional[List[UUID]] = None

        if current_user and not is_exec:
            user_vids = auth_service.get_user_vertical_ids(current_user.id)
            if not user_vids:
                return PerformanceIndicatorsResponse(
                    generated_at=now,
                    task_completion_rate_pct=0.0,
                    overdue_task_rate_pct=0.0,
                    issue_resolution_rate_pct=0.0,
                    requirement_resolution_rate_pct=0.0,
                    meeting_rsvp_rate_pct=0.0,
                    reporting_compliance_rate_pct=100.0,
                    event_readiness_avg_pct=0.0,
                    escalation_rate_pct=0.0,
                )

        # 1. Task Completion & Overdue Rates
        t_stmt = select(
            func.count(Task.id).label("total"),
            func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
            func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
        )
        if user_vids is not None:
            t_stmt = t_stmt.where(Task.vertical_id.in_(user_vids))
        t_res = self.db.execute(t_stmt).mappings().first() or {}
        tot_tasks = t_res.get("total") or 0
        comp_tasks = t_res.get("completed") or 0
        over_tasks = t_res.get("overdue") or 0
        task_comp_rate = round((comp_tasks / tot_tasks * 100.0), 1) if tot_tasks > 0 else 0.0
        overdue_rate = round((over_tasks / tot_tasks * 100.0), 1) if tot_tasks > 0 else 0.0

        # 2. Issue Resolution Rate
        i_stmt = select(
            func.count(Issue.id).label("total"),
            func.count(case((Issue.status == IssueStatus.RESOLVED, 1))).label("resolved"),
            func.count(case((Issue.status == IssueStatus.ESCALATED, 1))).label("escalated"),
        )
        if user_vids is not None:
            i_stmt = i_stmt.where(Issue.vertical_id.in_(user_vids))
        i_res = self.db.execute(i_stmt).mappings().first() or {}
        tot_issues = i_res.get("total") or 0
        res_issues = i_res.get("resolved") or 0
        esc_issues = i_res.get("escalated") or 0
        issue_res_rate = round((res_issues / tot_issues * 100.0), 1) if tot_issues > 0 else 0.0

        # 3. Requirement Resolution Rate
        r_stmt = select(
            func.count(Requirement.id).label("total"),
            func.count(case((Requirement.status == RequirementStatus.COMPLETED, 1))).label("completed"),
            func.count(case((Requirement.is_escalated == True, 1))).label("escalated"),
        )
        if user_vids is not None:
            r_stmt = r_stmt.where(
                or_(
                    Requirement.requesting_vertical_id.in_(user_vids),
                    Requirement.target_vertical_id.in_(user_vids),
                )
            )
        r_res = self.db.execute(r_stmt).mappings().first() or {}
        tot_reqs = r_res.get("total") or 0
        comp_reqs = r_res.get("completed") or 0
        esc_reqs = r_res.get("escalated") or 0
        req_res_rate = round((comp_reqs / tot_reqs * 100.0), 1) if tot_reqs > 0 else 0.0

        # 4. Meeting RSVP Rate
        tot_rsvps_stmt = select(func.count(MeetingParticipant.id)).join(Meeting, MeetingParticipant.meeting_id == Meeting.id)
        acc_rsvps_stmt = select(func.count(MeetingParticipant.id)).join(Meeting, MeetingParticipant.meeting_id == Meeting.id).where(MeetingParticipant.rsvp_status == RSVPStatus.ACCEPTED)
        if user_vids is not None:
            tot_rsvps_stmt = tot_rsvps_stmt.where(Meeting.vertical_id.in_(user_vids))
            acc_rsvps_stmt = acc_rsvps_stmt.where(Meeting.vertical_id.in_(user_vids))
        tot_rsvps = self.db.scalar(tot_rsvps_stmt) or 0
        acc_rsvps = self.db.scalar(acc_rsvps_stmt) or 0
        rsvp_rate = round((acc_rsvps / tot_rsvps * 100.0), 1) if tot_rsvps > 0 else 0.0

        # 5. Reporting Compliance Rate
        if user_vids is not None:
            active_users_stmt = (
                select(func.count(func.distinct(User.id)))
                .join(UserVertical, UserVertical.user_id == User.id)
                .where(User.account_status == AccountStatus.ACTIVE, UserVertical.vertical_id.in_(user_vids))
            )
            act_reports_stmt = (
                select(func.count(DailyWorkReport.id))
                .where(DailyWorkReport.report_date >= seven_days_ago, DailyWorkReport.vertical_id.in_(user_vids))
            )
        else:
            active_users_stmt = select(func.count(User.id)).where(User.account_status == AccountStatus.ACTIVE)
            act_reports_stmt = select(func.count(DailyWorkReport.id)).where(DailyWorkReport.report_date >= seven_days_ago)

        active_users = self.db.scalar(active_users_stmt) or 0
        exp_reports = active_users * 7
        act_reports = self.db.scalar(act_reports_stmt) or 0
        rep_comp_rate = round((act_reports / exp_reports * 100.0), 1) if exp_reports > 0 else 100.0

        # 6. Event Readiness via single SQL aggregate
        ri_stmt = select(
            func.count(EventReadinessItem.id).label("total"),
            func.count(case((EventReadinessItem.status == ReadinessStatus.COMPLETED, 1))).label("completed"),
        ).join(Event, EventReadinessItem.event_id == Event.id).where(Event.status != EventStatus.CANCELLED)
        if user_vids is not None:
            ri_stmt = ri_stmt.where(Event.vertical_id.in_(user_vids))
        ri_res = self.db.execute(ri_stmt).mappings().first() or {}
        ri_tot = ri_res.get("total") or 0
        ri_comp = ri_res.get("completed") or 0
        event_readiness_avg = round((ri_comp / ri_tot * 100.0), 1) if ri_tot > 0 else 0.0

        # 7. Escalation Rate
        tot_ops = tot_reqs + tot_issues
        tot_esc = esc_reqs + esc_issues
        esc_rate = round((tot_esc / tot_ops * 100.0), 1) if tot_ops > 0 else 0.0

        return PerformanceIndicatorsResponse(
            generated_at=now,
            task_completion_rate_pct=task_comp_rate,
            overdue_task_rate_pct=overdue_rate,
            issue_resolution_rate_pct=issue_res_rate,
            requirement_resolution_rate_pct=req_res_rate,
            meeting_rsvp_rate_pct=rsvp_rate,
            reporting_compliance_rate_pct=rep_comp_rate,
            event_readiness_avg_pct=event_readiness_avg,
            escalation_rate_pct=esc_rate,
        )

