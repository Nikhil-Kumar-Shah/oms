"""
Daily & Weekly Work Reports & Review Hierarchy Service Layer
Paradox Sports OMS - Phase 10J Review Hierarchy Refactor
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.issue import Issue, IssueStatus
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import (
    DailyReportHistory,
    DailyReportStatus,
    DailyReportTask,
    DailyWorkReport,
    WeeklyReport,
    WeeklyReportStatus,
)
from app.models.task import Task, TaskHealth, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.report import (
    DailyReportCreate,
    DailyReportHistoryResponse,
    DailyReportResponse,
    DailyReportReviewRequest,
    DailyReportTaskCreate,
    DailyReportTaskResponse,
    DailyReportUpdate,
    WeeklyIssueSummary,
    WeeklyReportCreate,
    WeeklyReportResponse,
    WeeklyReportReviewRequest,
    WeeklyRollupResponse,
    WeeklyTaskSummary,
)
from app.services.audit_service import AuditService
from app.services.authority_service import AuthorityService

logger = get_logger("app.services.report")


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.auth = AuthorityService(db)

    # -------------------------------------------------------------------------
    # Review Hierarchy & Authorization Engine
    # -------------------------------------------------------------------------

    def get_report_reviewer_role_and_scope(
        self, author_id: uuid.UUID, vertical_id: Optional[uuid.UUID]
    ) -> Tuple[List[str], Optional[uuid.UUID]]:
        """
        Determines the authorized reviewer role(s) and vertical division scope
        based on the strict operational hierarchy:
        - Volunteer -> Coordinator of the same vertical
        - Coordinator -> Super Coordinator of the same vertical
        - Super Coordinator -> Deputy Core OR Sports Core (org-wide)
        - Sports Core -> Deputy Core (org-wide)
        - Deputy Core -> Sports Core (org-wide)
        - Event Team is excluded from the reporting hierarchy.
        """
        role_names = self.auth.get_user_role_names(author_id)
        level = self.auth.get_user_operational_level(author_id)

        # Check for Event Team exclusion
        if "EVENT_TEAM" in role_names and level is None:
            raise ValidationException("Event Team accounts are excluded from the operational reporting hierarchy.")

        if level == 1 or "VOLUNTEER" in role_names:
            return ["COORDINATOR"], vertical_id
        elif level == 2 or "COORDINATOR" in role_names:
            return ["SUPER_COORDINATOR"], vertical_id
        elif level == 3 or "SUPER_COORDINATOR" in role_names:
            return ["DEPUTY_CORE", "SPORTS_CORE", "CORE"], None
        elif level == 5 or "SPORTS_CORE" in role_names or "CORE" in role_names:
            return ["DEPUTY_CORE"], None
        elif level == 4 or "DEPUTY_CORE" in role_names:
            return ["SPORTS_CORE", "CORE"], None
        else:
            # Default fallback for standard operational roles
            return ["COORDINATOR"], vertical_id

    def resolve_eligible_reviewers(
        self, author_id: uuid.UUID, vertical_id: Optional[uuid.UUID]
    ) -> List[User]:
        """Resolves active candidate reviewer users for a report."""
        try:
            target_roles, target_vid = self.get_report_reviewer_role_and_scope(author_id, vertical_id)
        except ValidationException:
            return []

        stmt = (
            select(User)
            .join(UserRole, User.id == UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(
                User.account_status == AccountStatus.ACTIVE,
                Role.name.in_(target_roles),
                User.id != author_id,  # Prevent self-review
            )
        )
        if target_vid is not None:
            stmt = stmt.join(UserVertical, User.id == UserVertical.user_id).where(
                UserVertical.vertical_id == target_vid
            )
        return list(self.db.scalars(stmt.distinct()).all())

    def can_user_review_report(self, reviewer: User, report: DailyWorkReport) -> bool:
        """
        Authoritative check verifying if the reviewer is permitted to review this report.
        Strictly prevents author self-review.
        """
        # SELF-REVIEW STRICTLY PREVENTED
        if report.user_id == reviewer.id:
            return False

        reviewer_roles = self.auth.get_user_role_names(reviewer.id)
        if "ADMIN" in reviewer_roles:
            return True

        try:
            expected_roles, expected_vid = self.get_report_reviewer_role_and_scope(
                report.user_id, report.vertical_id
            )
        except ValidationException:
            return False

        # Must have at least one of the expected roles
        if not reviewer_roles.intersection(set(expected_roles)):
            return False

        # If vertical-scoped, must belong to that vertical
        if expected_vid is not None:
            reviewer_vids = set(self.auth.get_user_vertical_ids(reviewer.id))
            if expected_vid not in reviewer_vids:
                return False

        return True

    def can_user_view_user_reports(self, viewer: User, target_user_id: uuid.UUID) -> bool:
        """
        Authoritative check verifying if the viewer is authorized to view reports of target_user_id.
        - Viewer viewing own reports: Always permitted.
        - Admin, Sports Core, Deputy Core, Core: Org-wide permitted.
        - Super Coordinator: Permitted for Coordinators and Volunteers in the same vertical.
        - Coordinator: Permitted for Volunteers in the same vertical.
        - Volunteer and Event Team: Only permitted to view own reports.
        """
        if viewer.id == target_user_id:
            return True

        if self.auth.is_executive_or_admin(viewer.id):
            return True

        viewer_roles = self.auth.get_user_role_names(viewer.id)
        if bool(viewer_roles.intersection({"SPORTS_CORE", "CORE", "DEPUTY_CORE", "ADMIN"})):
            return True

        viewer_level = self.auth.get_user_operational_level(viewer.id) or 1
        viewer_vids = set(self.auth.get_user_vertical_ids(viewer.id))

        target_vids = set(self.auth.get_user_vertical_ids(target_user_id))
        target_roles = self.auth.get_user_role_names(target_user_id)

        # Must share at least one vertical division
        shared_verticals = viewer_vids.intersection(target_vids)
        if not shared_verticals:
            return False

        if viewer_level == 3:  # Super Coordinator
            # Can view Coordinators and Volunteers in same vertical
            if bool(target_roles.intersection({"COORDINATOR", "VOLUNTEER"})):
                return True
        elif viewer_level == 2:  # Coordinator
            # Can view Volunteers in same vertical
            if "VOLUNTEER" in target_roles:
                return True

        return False

    # -------------------------------------------------------------------------
    # Daily Work Reports CRUD
    # -------------------------------------------------------------------------

    def create_daily_report(self, data: DailyReportCreate, user_id: uuid.UUID) -> DailyWorkReport:
        """
        Creates a daily work report for the authenticated user.
        Author, role, vertical, and report date are auto-derived from the logged-in user.
        Supports multi-task association and exact reviewer hierarchy resolution.
        """
        author = self.db.get(User, user_id)
        if not author:
            raise EntityNotFoundException("User", str(user_id))

        role_names = self.auth.get_user_role_names(user_id)
        if "EVENT_TEAM" in role_names and self.auth.get_user_operational_level(user_id) is None:
            raise ValidationException("Event Team accounts cannot submit operational work reports.")

        # 1. Derive Vertical
        user_vids = self.auth.get_user_vertical_ids(user_id)
        resolved_vertical_id = data.vertical_id
        if resolved_vertical_id:
            vert = self.db.get(Vertical, resolved_vertical_id)
            if not vert or vert.status != VerticalStatus.ACTIVE:
                raise ValidationException("Specified vertical does not exist or is inactive")
            if not self.auth.is_executive_or_admin(user_id) and resolved_vertical_id not in user_vids:
                raise ForbiddenException("You cannot submit a report for a vertical you do not belong to")
        else:
            if not user_vids and not self.auth.is_executive_or_admin(user_id):
                raise ValidationException("User is not assigned to any active vertical division")
            resolved_vertical_id = user_vids[0] if user_vids else None
            if not resolved_vertical_id:
                active_v = self.db.scalar(select(Vertical).where(Vertical.status == VerticalStatus.ACTIVE).limit(1))
                resolved_vertical_id = active_v.id if active_v else None

        if not resolved_vertical_id:
            raise ValidationException("Unable to derive active vertical division for report")

        # 2. Derive Report Date
        resolved_date = data.report_date or date.today()

        # 3. Check for existing report for this date
        stmt_exists = select(DailyWorkReport).where(
            DailyWorkReport.user_id == user_id,
            DailyWorkReport.report_date == resolved_date,
        )
        existing = self.db.scalar(stmt_exists)
        if existing:
            if existing.status in [DailyReportStatus.SUBMITTED, DailyReportStatus.REVIEWED]:
                raise ValidationException(
                    f"A daily report has already been submitted for date {resolved_date.isoformat()}"
                )
            elif existing.status == DailyReportStatus.RETURNED:
                raise ValidationException(
                    f"A report for date {resolved_date.isoformat()} was returned. Please edit and resubmit that report."
                )

        # 4. Resolve Reviewer via Hierarchy
        eligible_reviewers = self.resolve_eligible_reviewers(user_id, resolved_vertical_id)
        resolved_reviewer_id = eligible_reviewers[0].id if eligible_reviewers else None

        # 5. Collect and validate tasks
        task_notes_map: Dict[uuid.UUID, Optional[str]] = {}
        if data.tasks:
            for item in data.tasks:
                task_notes_map[item.task_id] = item.progress_notes
        if data.task_ids:
            for tid in data.task_ids:
                if tid not in task_notes_map:
                    task_notes_map[tid] = None
        if data.assigned_task_id:
            if data.assigned_task_id not in task_notes_map:
                task_notes_map[data.assigned_task_id] = data.tasks_completed

        if task_notes_map:
            tids = list(task_notes_map.keys())
            stmt_tasks = select(Task).where(Task.id.in_(tids))
            tasks = list(self.db.scalars(stmt_tasks).all())
            found_ids = {t.id for t in tasks}
            for tid in tids:
                if tid not in found_ids:
                    raise ValidationException(f"Task with ID {tid} not found")

            # Validate ownership: must be assigned to user or in user vertical
            if not self.auth.is_executive_or_admin(user_id):
                for t in tasks:
                    if t.assigned_to_id != user_id and t.vertical_id not in set(user_vids):
                        raise ForbiddenException(f"Task '{t.title}' is not assigned to you or your vertical")

        report_status = DailyReportStatus.SUBMITTED if data.submit_now else DailyReportStatus.DRAFT
        submitted_at = datetime.now(timezone.utc) if data.submit_now else None

        report = DailyWorkReport(
            user_id=user_id,
            vertical_id=resolved_vertical_id,
            report_date=resolved_date,
            work_summary=data.work_summary.strip(),
            tasks_completed=data.tasks_completed,
            blockers=data.blockers,
            issues=data.issues,
            next_actions=data.next_actions,
            evidence_links=data.evidence_links,
            status=report_status,
            reviewer_id=resolved_reviewer_id,
            submitted_at=submitted_at,
        )
        self.db.add(report)
        self.db.flush()

        # Link tasks in daily_report_tasks
        for tid, notes in task_notes_map.items():
            rt = DailyReportTask(
                report_id=report.id,
                task_id=tid,
                progress_notes=notes,
            )
            self.db.add(rt)

        # Audit & History entry
        history_action = "SUBMITTED" if data.submit_now else "DRAFT"
        history = DailyReportHistory(
            report_id=report.id,
            actor_id=user_id,
            action=history_action,
            comments=data.work_summary[:200],
        )
        self.db.add(history)
        self.db.flush()

        self.audit.log(
            action=f"DAILY_REPORT_{history_action}",
            resource_type="DAILY_WORK_REPORT",
            resource_id=str(report.id),
            outcome="SUCCESS",
            actor_id=user_id,
            details={"report_date": report.report_date.isoformat(), "status": report.status.value},
        )

        logger.info(f"Created DailyWorkReport (id={report.id}, user_id={user_id}, date={report.report_date}, status={report.status})")
        return self.get_daily_report_by_id(report.id)

    def get_daily_report_by_id(self, report_id: uuid.UUID, current_user: Optional[User] = None) -> DailyWorkReport:
        """Retrieves daily work report with eager-loaded tasks and history."""
        stmt = (
            select(DailyWorkReport)
            .where(DailyWorkReport.id == report_id)
            .options(
                selectinload(DailyWorkReport.user),
                selectinload(DailyWorkReport.vertical),
                selectinload(DailyWorkReport.reviewer),
                selectinload(DailyWorkReport.reviewed_by),
                selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
                selectinload(DailyWorkReport.history_entries).selectinload(DailyReportHistory.actor),
            )
        )
        report = self.db.scalar(stmt)
        if not report:
            raise EntityNotFoundException("DailyWorkReport", str(report_id))

        if current_user:
            if not self.can_user_view_user_reports(current_user, report.user_id) and not self.can_user_review_report(current_user, report):
                raise ForbiddenException("Access denied: You are not authorized to view this work report")

        return report

    def list_daily_reports(
        self,
        current_user: User,
        user_id: Optional[uuid.UUID] = None,
        vertical_id: Optional[uuid.UUID] = None,
        status: Optional[DailyReportStatus] = None,
        report_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[DailyWorkReport], int]:
        """
        Lists daily work reports within authorized scope.
        Applies a 14-day rolling retention window for normal users;
        Sports Core, Deputy Core, and Admin retain complete historical access.
        """
        stmt = select(DailyWorkReport).options(
            selectinload(DailyWorkReport.user),
            selectinload(DailyWorkReport.vertical),
            selectinload(DailyWorkReport.reviewer),
            selectinload(DailyWorkReport.reviewed_by),
            selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
            selectinload(DailyWorkReport.history_entries).selectinload(DailyReportHistory.actor),
        )

        is_exec = self.auth.is_executive_or_admin(current_user.id)
        role_names = self.auth.get_user_role_names(current_user.id)
        is_core = bool(role_names.intersection({"SPORTS_CORE", "CORE", "DEPUTY_CORE", "ADMIN"}))

        # 14-day retention rule for non-executives
        if not is_core:
            retention_cutoff = date.today() - timedelta(days=14)
            stmt = stmt.where(DailyWorkReport.report_date >= retention_cutoff)

        if user_id and user_id != current_user.id:
            if not self.can_user_view_user_reports(current_user, user_id):
                raise ForbiddenException("Access denied: You are not authorized to view this user's daily reports")

        if not is_exec:
            user_vids = self.auth.get_user_vertical_ids(current_user.id)
            user_level = self.auth.get_user_operational_level(current_user.id) or 1

            if user_level == 1:  # Volunteer
                stmt = stmt.where(DailyWorkReport.user_id == current_user.id)
            elif user_level == 2:  # Coordinator: sees Volunteers in vertical or self
                if not user_id:
                    stmt = stmt.where(
                        or_(
                            DailyWorkReport.user_id == current_user.id,
                            DailyWorkReport.vertical_id.in_(user_vids),
                        )
                    )
                else:
                    stmt = stmt.where(DailyWorkReport.user_id == user_id)
            elif user_level == 3:  # Super Coordinator: sees Coordinators and Volunteers in vertical
                if not user_id:
                    stmt = stmt.where(
                        or_(
                            DailyWorkReport.user_id == current_user.id,
                            DailyWorkReport.vertical_id.in_(user_vids),
                        )
                    )
                else:
                    stmt = stmt.where(DailyWorkReport.user_id == user_id)
        else:
            if user_id:
                stmt = stmt.where(DailyWorkReport.user_id == user_id)
            if vertical_id:
                stmt = stmt.where(DailyWorkReport.vertical_id == vertical_id)

        if status:
            stmt = stmt.where(DailyWorkReport.status == status)
        if report_date:
            stmt = stmt.where(DailyWorkReport.report_date == report_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(DailyWorkReport.report_date), desc(DailyWorkReport.created_at)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def resubmit_daily_report(
        self, report_id: uuid.UUID, data: DailyReportUpdate, actor_id: uuid.UUID
    ) -> DailyWorkReport:
        """
        Allows an author to correct and resubmit a report that was RETURNED or in DRAFT.
        """
        report = self.get_daily_report_by_id(report_id)
        if report.user_id != actor_id:
            raise ForbiddenException("You are not authorized to edit or resubmit this report")

        if report.status not in [DailyReportStatus.RETURNED, DailyReportStatus.DRAFT]:
            raise ValidationException("Only reports with RETURNED or DRAFT status can be resubmitted")

        if data.work_summary:
            report.work_summary = data.work_summary.strip()
        if data.blockers is not None:
            report.blockers = data.blockers
        if data.issues is not None:
            report.issues = data.issues
        if data.next_actions is not None:
            report.next_actions = data.next_actions
        if data.evidence_links is not None:
            report.evidence_links = data.evidence_links
        if data.tasks_completed is not None:
            report.tasks_completed = data.tasks_completed

        # Update tasks if provided
        task_notes_map: Dict[uuid.UUID, Optional[str]] = {}
        if data.tasks is not None:
            for item in data.tasks:
                task_notes_map[item.task_id] = item.progress_notes
        elif data.task_ids is not None:
            for tid in data.task_ids:
                task_notes_map[tid] = None

        if data.tasks is not None or data.task_ids is not None:
            # Clear old tasks
            for rt in list(report.report_tasks):
                self.db.delete(rt)
            self.db.flush()

            # Add updated tasks
            for tid, notes in task_notes_map.items():
                rt = DailyReportTask(report_id=report.id, task_id=tid, progress_notes=notes)
                self.db.add(rt)

        report.status = DailyReportStatus.SUBMITTED
        report.submitted_at = datetime.now(timezone.utc)

        history = DailyReportHistory(
            report_id=report.id,
            actor_id=actor_id,
            action="RESUBMITTED",
            comments="Report corrected and resubmitted for supervisor review",
        )
        self.db.add(history)
        self.db.flush()

        self.audit.log(
            action="DAILY_REPORT_RESUBMIT",
            resource_type="DAILY_WORK_REPORT",
            resource_id=str(report.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"status": report.status.value},
        )

        return self.get_daily_report_by_id(report.id)

    def review_daily_report(
        self, report_id: uuid.UUID, reviewer: User, data: DailyReportReviewRequest
    ) -> DailyWorkReport:
        """
        Applies supervisor review (Approve or Return).
        Enforces strict review hierarchy and forbids self-review.
        """
        report = self.get_daily_report_by_id(report_id)

        if not self.can_user_review_report(reviewer, report):
            raise ForbiddenException("You are not authorized to review this report under the operational hierarchy")

        if data.status not in [DailyReportStatus.REVIEWED, DailyReportStatus.RETURNED]:
            raise ValidationException("Invalid review status. Must be REVIEWED or RETURNED")

        if data.status == DailyReportStatus.RETURNED and not (data.review_comments and data.review_comments.strip()):
            raise ValidationException("Review comments are required when returning a report for correction")

        report.status = data.status
        report.reviewer_id = reviewer.id
        report.reviewed_by_id = reviewer.id
        report.review_comments = data.review_comments.strip() if data.review_comments else None
        report.reviewed_at = datetime.now(timezone.utc)

        action_name = "APPROVED" if data.status == DailyReportStatus.REVIEWED else "RETURNED"
        history = DailyReportHistory(
            report_id=report.id,
            actor_id=reviewer.id,
            action=action_name,
            comments=data.review_comments,
        )
        self.db.add(history)
        self.db.flush()

        self.audit.log(
            action=f"DAILY_REPORT_{action_name}",
            resource_type="DAILY_WORK_REPORT",
            resource_id=str(report.id),
            outcome="SUCCESS",
            actor_id=reviewer.id,
            details={"status": report.status.value, "comments": report.review_comments},
        )

        return self.get_daily_report_by_id(report.id)

    def get_supervisor_review_queue(
        self, current_user: User, skip: int = 0, limit: int = 50
    ) -> Tuple[List[DailyWorkReport], int]:
        """
        Retrieves pending submitted reports that the current user is authorized to review.
        """
        reviewer_roles = self.auth.get_user_role_names(current_user.id)
        is_admin = "ADMIN" in reviewer_roles

        stmt = (
            select(DailyWorkReport)
            .where(
                DailyWorkReport.status == DailyReportStatus.SUBMITTED,
                DailyWorkReport.user_id != current_user.id,  # Never self-review
            )
            .options(
                selectinload(DailyWorkReport.user),
                selectinload(DailyWorkReport.vertical),
                selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
            )
        )

        if not is_admin:
            level = self.auth.get_user_operational_level(current_user.id)
            user_vids = self.auth.get_user_vertical_ids(current_user.id)

            if level == 2:  # Coordinator: sees Volunteers in same vertical
                sub_roles = ["VOLUNTEER"]
                stmt = (
                    stmt.join(UserRole, DailyWorkReport.user_id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(
                        Role.name.in_(sub_roles),
                        DailyWorkReport.vertical_id.in_(user_vids),
                    )
                )
            elif level == 3:  # Super Coordinator: sees Coordinators in same vertical
                sub_roles = ["COORDINATOR"]
                stmt = (
                    stmt.join(UserRole, DailyWorkReport.user_id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(
                        Role.name.in_(sub_roles),
                        DailyWorkReport.vertical_id.in_(user_vids),
                    )
                )
            elif level == 4:  # Deputy Core: sees Super Coordinators and Sports Core
                sub_roles = ["SUPER_COORDINATOR", "SPORTS_CORE", "CORE"]
                stmt = (
                    stmt.join(UserRole, DailyWorkReport.user_id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(Role.name.in_(sub_roles))
                )
            elif level == 5:  # Sports Core: sees Super Coordinators and Deputy Core
                sub_roles = ["SUPER_COORDINATOR", "DEPUTY_CORE"]
                stmt = (
                    stmt.join(UserRole, DailyWorkReport.user_id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(Role.name.in_(sub_roles))
                )
            else:
                # Volunteers and Event Team have no review queue
                return [], 0

        stmt = stmt.distinct()
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(DailyWorkReport.submitted_at), desc(DailyWorkReport.report_date)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())
        return items, total

    # -------------------------------------------------------------------------
    # Automatic Weekly Report Generation & Hierarchy
    # -------------------------------------------------------------------------

    def get_or_generate_weekly_report(
        self, user_id: uuid.UUID, week_start_date: date
    ) -> WeeklyReport:
        """
        Automatically generates a 7-day weekly report from daily reports submitted
        by the user within that 7-day window.
        """
        user = self.db.get(User, user_id)
        if not user:
            raise EntityNotFoundException("User", str(user_id))

        week_end_date = week_start_date + timedelta(days=6)

        # 1. Check existing WeeklyReport
        stmt_wr = select(WeeklyReport).where(
            WeeklyReport.user_id == user_id,
            WeeklyReport.week_start_date == week_start_date,
        )
        existing = self.db.scalar(stmt_wr)

        # 2. Fetch daily reports in the window
        daily_stmt = (
            select(DailyWorkReport)
            .options(
                selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
            )
            .where(
                DailyWorkReport.user_id == user_id,
                DailyWorkReport.report_date >= week_start_date,
                DailyWorkReport.report_date <= week_end_date,
            )
            .order_by(DailyWorkReport.report_date.asc())
        )
        daily_reports = list(self.db.scalars(daily_stmt).all())

        # Consolidate details
        work_parts = []
        blocker_parts = []
        issue_parts = []
        action_parts = []
        for dr in daily_reports:
            work_parts.append(f"[{dr.report_date}]: {dr.work_summary}")
            if dr.blockers:
                blocker_parts.append(f"[{dr.report_date}]: {dr.blockers}")
            if dr.issues:
                issue_parts.append(f"[{dr.report_date}]: {dr.issues}")
            if dr.next_actions:
                action_parts.append(f"[{dr.report_date}]: {dr.next_actions}")

        summary = "\n".join(work_parts) if work_parts else "No daily reports submitted for this period."
        blockers = "\n".join(blocker_parts) if blocker_parts else None
        issues = "\n".join(issue_parts) if issue_parts else None
        actions = "\n".join(action_parts) if action_parts else None

        user_vids = self.auth.get_user_vertical_ids(user_id)
        vertical_id = user_vids[0] if user_vids else None
        if not vertical_id:
            first_v = self.db.scalar(select(Vertical).where(Vertical.status == VerticalStatus.ACTIVE).limit(1))
            vertical_id = first_v.id if first_v else None

        if not existing:
            weekly = WeeklyReport(
                user_id=user_id,
                vertical_id=vertical_id,
                week_start_date=week_start_date,
                week_end_date=week_end_date,
                summary=summary,
                completed_work=summary,
                blockers=blockers,
                issues=issues,
                priorities_next_week=actions,
                status=WeeklyReportStatus.SUBMITTED,
                submitted_at=datetime.now(timezone.utc),
            )
            self.db.add(weekly)
            self.db.flush()
            return weekly
        else:
            # Sync summary if not yet reviewed
            if existing.status in [WeeklyReportStatus.SUBMITTED, WeeklyReportStatus.DRAFT]:
                existing.summary = summary
                existing.completed_work = summary
                existing.blockers = blockers
                existing.issues = issues
                existing.priorities_next_week = actions
                self.db.flush()
            return existing

    def list_weekly_reports(
        self,
        current_user: User,
        user_id: Optional[uuid.UUID] = None,
        vertical_id: Optional[uuid.UUID] = None,
        status: Optional[WeeklyReportStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[WeeklyReport], int]:
        """
        Lists weekly reports applying the exact review hierarchy and 14-day retention rule.
        """
        stmt = select(WeeklyReport).options(
            selectinload(WeeklyReport.user),
            selectinload(WeeklyReport.vertical),
            selectinload(WeeklyReport.reviewer),
            selectinload(WeeklyReport.reviewed_by),
        )

        is_exec = self.auth.is_executive_or_admin(current_user.id)
        role_names = self.auth.get_user_role_names(current_user.id)
        is_core = bool(role_names.intersection({"SPORTS_CORE", "CORE", "DEPUTY_CORE", "ADMIN"}))

        if not is_core:
            retention_cutoff = date.today() - timedelta(days=14)
            stmt = stmt.where(WeeklyReport.week_start_date >= retention_cutoff)

        if user_id and user_id != current_user.id:
            if not self.can_user_view_user_reports(current_user, user_id):
                raise ForbiddenException("Access denied: You are not authorized to view this user's weekly reports")

        if not is_exec:
            user_vids = self.auth.get_user_vertical_ids(current_user.id)
            user_level = self.auth.get_user_operational_level(current_user.id) or 1

            if user_level == 1:  # Volunteer: only self
                stmt = stmt.where(WeeklyReport.user_id == current_user.id)
            elif user_level in [2, 3]:  # Coordinator & Super Coordinator: vertical subordinates + self
                stmt = stmt.where(
                    or_(
                        WeeklyReport.user_id == current_user.id,
                        WeeklyReport.vertical_id.in_(user_vids),
                    )
                )
                if user_id:
                    stmt = stmt.where(WeeklyReport.user_id == user_id)
        else:
            if user_id:
                stmt = stmt.where(WeeklyReport.user_id == user_id)
            if vertical_id:
                stmt = stmt.where(WeeklyReport.vertical_id == vertical_id)

        if status:
            stmt = stmt.where(WeeklyReport.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(WeeklyReport.week_start_date), desc(WeeklyReport.created_at)).offset(skip).limit(limit)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def review_weekly_report(
        self, report_id: uuid.UUID, reviewer: User, data: WeeklyReportReviewRequest
    ) -> WeeklyReport:
        """Applies supervisor review to weekly report under hierarchical rules."""
        report = self.get_weekly_report_by_id(report_id)

        if report.user_id == reviewer.id:
            raise ForbiddenException("Self-review violation: Authors cannot review their own weekly reports")

        report.status = data.status
        report.reviewer_id = reviewer.id
        report.reviewed_by_id = reviewer.id
        report.supervisor_comments = data.supervisor_comments.strip() if data.supervisor_comments else None
        report.reviewed_at = datetime.now(timezone.utc)

        self.db.flush()

        self.audit.log(
            action="WEEKLY_REPORT_REVIEW",
            resource_type="WEEKLY_REPORT",
            resource_id=str(report.id),
            outcome="SUCCESS",
            actor_id=reviewer.id,
            details={"review_status": data.status.value},
        )

        return report

    def get_weekly_report_by_id(self, report_id: uuid.UUID, current_user: Optional[User] = None) -> WeeklyReport:
        stmt = (
            select(WeeklyReport)
            .where(WeeklyReport.id == report_id)
            .options(
                selectinload(WeeklyReport.user),
                selectinload(WeeklyReport.vertical),
                selectinload(WeeklyReport.reviewer),
                selectinload(WeeklyReport.reviewed_by),
            )
        )
        report = self.db.scalar(stmt)
        if not report:
            raise EntityNotFoundException("WeeklyReport", str(report_id))

        if current_user:
            if not self.can_user_view_user_reports(current_user, report.user_id):
                raise ForbiddenException("Access denied: You are not authorized to view this weekly report")

        return report

    # -------------------------------------------------------------------------
    # Legacy Dynamic Weekly Rollup Layer
    # -------------------------------------------------------------------------

    def generate_weekly_rollup(
        self,
        start_date: date,
        end_date: date,
        vertical_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> WeeklyRollupResponse:
        vert = self.db.get(Vertical, vertical_id) if vertical_id else None
        target_user = self.db.get(User, user_id) if user_id else None

        daily_stmt = (
            select(DailyWorkReport)
            .options(
                selectinload(DailyWorkReport.user),
                selectinload(DailyWorkReport.vertical),
                selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
            )
            .where(
                DailyWorkReport.report_date >= start_date,
                DailyWorkReport.report_date <= end_date,
            )
        )
        if vertical_id:
            daily_stmt = daily_stmt.where(DailyWorkReport.vertical_id == vertical_id)
        if user_id:
            daily_stmt = daily_stmt.where(DailyWorkReport.user_id == user_id)

        daily_records = list(self.db.scalars(daily_stmt.order_by(DailyWorkReport.report_date.asc())).all())

        daily_responses = []
        collected_blockers = []
        collected_achievements = []

        for d in daily_records:
            t_responses = [
                DailyReportTaskResponse(
                    task_id=rt.task_id,
                    task_title=rt.task.title if rt.task else "Task",
                    task_status=rt.task.status.value if rt.task else "UNKNOWN",
                    progress_notes=rt.progress_notes,
                )
                for rt in d.report_tasks
            ]
            daily_responses.append(
                DailyReportResponse(
                    id=d.id,
                    user_id=d.user_id,
                    author_id=d.user_id,
                    username=d.user.username if d.user else None,
                    user_full_name=d.user.full_name if d.user else None,
                    vertical_id=d.vertical_id,
                    vertical_name=d.vertical.name if d.vertical else None,
                    report_date=d.report_date,
                    work_summary=d.work_summary,
                    tasks=t_responses,
                    tasks_completed=d.tasks_completed,
                    blockers=d.blockers,
                    issues=d.issues,
                    next_actions=d.next_actions,
                    evidence_links=d.evidence_links,
                    status=d.status,
                    reviewer_id=d.reviewer_id,
                    review_comments=d.review_comments,
                    submitted_at=d.submitted_at,
                    reviewed_at=d.reviewed_at,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
            )
            if d.blockers and d.blockers.strip():
                collected_blockers.append(f"[{d.report_date}] {d.user.full_name if d.user else 'User'}: {d.blockers.strip()}")
            if d.tasks_completed and d.tasks_completed.strip():
                collected_achievements.append(f"[{d.report_date}] {d.tasks_completed.strip()}")

        task_stmt = select(Task).options(selectinload(Task.assigned_to))
        if vertical_id:
            task_stmt = task_stmt.where(Task.vertical_id == vertical_id)
        if user_id:
            task_stmt = task_stmt.where(Task.assigned_to_id == user_id)

        tasks = list(self.db.scalars(task_stmt).all())
        completed_tasks: List[WeeklyTaskSummary] = []
        incomplete_tasks: List[WeeklyTaskSummary] = []

        for t in tasks:
            ts = WeeklyTaskSummary(
                id=t.id,
                title=t.title,
                status=t.status.value,
                priority=t.priority.value,
                assigned_to_name=t.assigned_to.full_name if t.assigned_to else None,
                deadline=t.deadline,
            )
            if t.status == TaskStatus.COMPLETED:
                completed_tasks.append(ts)
            else:
                incomplete_tasks.append(ts)

            if (t.status == TaskStatus.BLOCKED or t.health == TaskHealth.BLOCKED) and t.blockers:
                collected_blockers.append(f"[Task Blocker - '{t.title}']: {t.blockers}")

        issue_stmt = select(Issue)
        if vertical_id:
            issue_stmt = issue_stmt.where(Issue.vertical_id == vertical_id)
        issues = list(self.db.scalars(issue_stmt).all())

        major_issues: List[WeeklyIssueSummary] = [
            WeeklyIssueSummary(
                id=iss.id,
                title=iss.title,
                status=iss.status.value,
                sensitivity=iss.sensitivity.value if hasattr(iss.sensitivity, "value") else str(iss.sensitivity),
            )
            for iss in issues
            if iss.status != IssueStatus.CLOSED
        ]

        existing_report = None
        if user_id:
            stmt_wr = select(WeeklyReport).where(
                WeeklyReport.user_id == user_id,
                WeeklyReport.week_start_date == start_date,
            )
            wr = self.db.scalar(stmt_wr)
            if wr:
                existing_report = WeeklyReportResponse(
                    id=wr.id,
                    user_id=wr.user_id,
                    author_id=wr.user_id,
                    username=wr.user.username if wr.user else None,
                    user_full_name=wr.user.full_name if wr.user else None,
                    vertical_id=wr.vertical_id,
                    vertical_name=wr.vertical.name if wr.vertical else None,
                    week_start_date=wr.week_start_date,
                    week_end_date=wr.week_end_date,
                    summary=wr.summary,
                    completed_work=wr.completed_work,
                    outstanding_work=wr.outstanding_work,
                    blockers=wr.blockers,
                    issues=wr.issues,
                    priorities_next_week=wr.priorities_next_week,
                    supervisor_comments=wr.supervisor_comments,
                    reviewer_id=wr.reviewer_id,
                    status=wr.status,
                    submitted_at=wr.submitted_at,
                    reviewed_at=wr.reviewed_at,
                    created_at=wr.created_at,
                    updated_at=wr.updated_at,
                )

        return WeeklyRollupResponse(
            start_date=start_date,
            end_date=end_date,
            vertical_id=vertical_id,
            vertical_name=vert.name if vert else None,
            user_id=user_id,
            user_name=target_user.full_name if target_user else None,
            daily_reports_count=len(daily_records),
            daily_reports_submitted=daily_responses,
            completed_tasks_count=len(completed_tasks),
            completed_tasks=completed_tasks,
            incomplete_tasks_count=len(incomplete_tasks),
            incomplete_tasks=incomplete_tasks,
            blockers_count=len(collected_blockers),
            blockers=collected_blockers,
            major_issues_count=len(major_issues),
            major_issues=major_issues,
            achievements=collected_achievements,
            existing_weekly_report=existing_report,
        )
