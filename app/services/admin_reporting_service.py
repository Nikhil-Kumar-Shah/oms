"""
Administrative Reporting Service Layer
Generates authoritative operational intelligence and compliance reports from PostgreSQL.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload
from app.models.event import Event, EventReadinessItem, EventStatus, ReadinessStatus
from app.models.governance import OwnershipTransfer, TransferStatus
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import Meeting, MeetingParticipant, RSVPStatus
from app.models.organization import Vertical
from app.models.report import DailyWorkReport, WeeklyReport
from app.models.requirement import Requirement, RequirementStatus
from app.models.task import Task, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.analytics import AdminReportResponse


class AdminReportingService:
    """Generates structured administrative reports over PostgreSQL records."""

    def __init__(self, db: Session):
        self.db = db

    def get_task_completion_report(self, vertical_id: Optional[UUID] = None) -> AdminReportResponse:
        now = datetime.now(timezone.utc)
        stmt = (
            select(
                Vertical.id.label("vertical_id"),
                Vertical.name.label("vertical_name"),
                func.count(Task.id).label("total_tasks"),
                func.count(case((Task.status == TaskStatus.COMPLETED, 1))).label("completed"),
                func.count(case((Task.status == TaskStatus.IN_PROGRESS, 1))).label("in_progress"),
                func.count(case((Task.status == TaskStatus.BLOCKED, 1))).label("blocked"),
                func.count(case(((Task.deadline < now) & (Task.status != TaskStatus.COMPLETED) & (Task.status != TaskStatus.CANCELLED), 1))).label("overdue"),
            )
            .outerjoin(Task, Vertical.id == Task.vertical_id)
            .group_by(Vertical.id, Vertical.name)
            .order_by(Vertical.name.asc())
        )
        if vertical_id:
            stmt = stmt.where(Vertical.id == vertical_id)

        rows = self.db.execute(stmt).mappings().all()
        records = []
        tot_all, tot_comp = 0, 0
        for r in rows:
            t = r["total_tasks"]
            c = r["completed"]
            tot_all += t
            tot_comp += c
            rate = round((c / t * 100.0), 1) if t > 0 else 0.0
            records.append({
                "vertical_id": str(r["vertical_id"]),
                "vertical_name": r["vertical_name"],
                "total_tasks": t,
                "completed": c,
                "in_progress": r["in_progress"],
                "blocked": r["blocked"],
                "overdue": r["overdue"],
                "completion_rate_pct": rate,
            })

        overall_rate = round((tot_comp / tot_all * 100.0), 1) if tot_all > 0 else 0.0
        return AdminReportResponse(
            report_name="Task Completion & Workload Report",
            generated_at=now,
            total_records=len(records),
            summary={"total_tasks": tot_all, "total_completed": tot_comp, "overall_completion_rate_pct": overall_rate},
            records=records,
        )

    def get_event_readiness_report(self) -> AdminReportResponse:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Event)
            .options(selectinload(Event.readiness_items), selectinload(Event.vertical))
            .order_by(Event.planned_date.asc())
        )
        events = list(self.db.scalars(stmt).all())
        records = []
        for e in events:
            tot_items = len(e.readiness_items)
            comp_items = sum(1 for item in e.readiness_items if item.status == ReadinessStatus.COMPLETED)
            pct = round((comp_items / tot_items * 100.0), 1) if tot_items > 0 else 0.0
            records.append({
                "event_id": str(e.id),
                "event_name": e.name,
                "vertical_name": e.vertical.name if e.vertical else None,
                "event_type": e.event_type.value,
                "status": e.status.value,
                "planned_date": e.planned_date.isoformat() if e.planned_date else None,
                "location": e.location,
                "total_checkpoints": tot_items,
                "completed_checkpoints": comp_items,
                "readiness_pct": pct,
            })

        return AdminReportResponse(
            report_name="Event Readiness & Checklist Report",
            generated_at=now,
            total_records=len(records),
            summary={"total_events": len(records)},
            records=records,
        )

    def get_issue_escalation_report(self) -> AdminReportResponse:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.vertical),
                selectinload(Issue.raised_by),
                selectinload(Issue.assigned_to),
            )
            .order_by(Issue.created_at.desc())
        )
        issues = list(self.db.scalars(stmt).all())
        records = []
        open_cnt, esc_cnt = 0, 0
        for i in issues:
            if i.status == IssueStatus.OPEN:
                open_cnt += 1
            elif i.status == IssueStatus.ESCALATED:
                esc_cnt += 1

            records.append({
                "issue_id": str(i.id),
                "title": i.title,
                "vertical_name": i.vertical.name if i.vertical else None,
                "sensitivity": i.sensitivity.value,
                "status": i.status.value,
                "escalation_target": i.escalation_target,
                "raised_by": i.raised_by.username if i.raised_by else None,
                "assigned_to": i.assigned_to.username if i.assigned_to else None,
                "created_at": i.created_at.isoformat(),
            })

        return AdminReportResponse(
            report_name="Issue & Escalation Register Report",
            generated_at=now,
            total_records=len(records),
            summary={"total_issues": len(records), "open_issues": open_cnt, "escalated_issues": esc_cnt},
            records=records,
        )

    def get_meeting_attendance_report(self) -> AdminReportResponse:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Meeting)
            .options(selectinload(Meeting.participants))
            .order_by(Meeting.meeting_date.desc())
        )
        meetings = list(self.db.scalars(stmt).all())
        records = []
        for m in meetings:
            tot = len(m.participants)
            accepted = sum(1 for p in m.participants if p.rsvp_status == RSVPStatus.ACCEPTED)
            declined = sum(1 for p in m.participants if p.rsvp_status == RSVPStatus.DECLINED)
            pending = sum(1 for p in m.participants if p.rsvp_status == RSVPStatus.PENDING)
            pct = round((accepted / tot * 100.0), 1) if tot > 0 else 0.0

            records.append({
                "meeting_id": str(m.id),
                "title": m.title,
                "meeting_date": m.meeting_date.isoformat(),
                "meeting_type": m.meeting_type.value,
                "status": m.status.value,
                "total_invited": tot,
                "accepted": accepted,
                "declined": declined,
                "pending": pending,
                "acceptance_rate_pct": pct,
            })

        return AdminReportResponse(
            report_name="Meeting Participation & RSVP Report",
            generated_at=now,
            total_records=len(records),
            summary={"total_meetings": len(records)},
            records=records,
        )

    def get_reporting_compliance_report(self, days: int = 7) -> AdminReportResponse:
        now = datetime.now(timezone.utc)
        today = date.today()
        since = today - timedelta(days=days)

        users = list(self.db.scalars(select(User).where(User.account_status == AccountStatus.ACTIVE)).all())

        # Single bulk aggregation query instead of per-user query loop
        counts_stmt = (
            select(DailyWorkReport.user_id, func.count(DailyWorkReport.id).label("cnt"))
            .where(DailyWorkReport.report_date >= since)
            .group_by(DailyWorkReport.user_id)
        )
        user_counts = dict(self.db.execute(counts_stmt).all())

        records = []
        tot_exp = len(users) * days
        tot_act = 0

        for u in users:
            count = user_counts.get(u.id, 0)
            tot_act += count
            pct = round((count / days * 100.0), 1) if days > 0 else 0.0
            records.append({
                "user_id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "expected_reports": days,
                "submitted_reports": count,
                "compliance_pct": pct,
            })

        overall_pct = round((tot_act / tot_exp * 100.0), 1) if tot_exp > 0 else 100.0
        return AdminReportResponse(
            report_name=f"Operational Reporting Compliance Report (Last {days} Days)",
            generated_at=now,
            total_records=len(records),
            summary={
                "total_users": len(users),
                "expected_reports": tot_exp,
                "submitted_reports": tot_act,
                "overall_compliance_pct": overall_pct,
            },
            records=records,
        )
