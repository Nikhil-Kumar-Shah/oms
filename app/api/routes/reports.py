"""
Daily & Weekly Work Reports & Review Hierarchy API Endpoints
Paradox Sports OMS - Phase 10J Review Hierarchy Refactor
"""

import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.exceptions import ForbiddenException
from app.models.report import (
    DailyReportHistory,
    DailyReportStatus,
    DailyReportTask,
    DailyWorkReport,
    WeeklyReportStatus,
)
from app.models.user import User
from app.schemas.report import (
    DailyReportCreate,
    DailyReportHistoryResponse,
    DailyReportListResponse,
    DailyReportResponse,
    DailyReportReviewRequest,
    DailyReportTaskResponse,
    DailyReportUpdate,
    WeeklyReportCreate,
    WeeklyReportListResponse,
    WeeklyReportResponse,
    WeeklyReportReviewRequest,
    WeeklyRollupResponse,
)
from app.services.authority_service import AuthorityService
from app.services.report_service import ReportService

reports_router = APIRouter(prefix="/reports", tags=["Daily & Weekly Reports"])


def _format_daily_report_response(report, db: Optional[Session] = None) -> DailyReportResponse:
    """Helper to convert daily report model to response schema."""
    user_role_str = None
    if db and report.user_id:
        auth = AuthorityService(db)
        roles = auth.get_user_role_names(report.user_id)
        user_role_str = list(roles)[0] if roles else None

    # Tasks
    tasks_list = []
    if hasattr(report, "report_tasks") and report.report_tasks:
        for rt in report.report_tasks:
            tasks_list.append(
                DailyReportTaskResponse(
                    task_id=rt.task_id,
                    task_title=rt.task.title if rt.task else "Task",
                    task_status=rt.task.status.value if (rt.task and hasattr(rt.task.status, "value")) else str(rt.task.status) if rt.task else "PENDING",
                    progress_notes=rt.progress_notes,
                )
            )

    # History
    history_list = []
    if hasattr(report, "history_entries") and report.history_entries:
        for h in report.history_entries:
            history_list.append(
                DailyReportHistoryResponse(
                    id=h.id,
                    report_id=h.report_id,
                    actor_id=h.actor_id,
                    actor_username=h.actor.username if h.actor else None,
                    action=h.action,
                    comments=h.comments,
                    created_at=h.created_at,
                )
            )

    return DailyReportResponse(
        id=report.id,
        user_id=report.user_id,
        author_id=report.user_id,
        user_role=user_role_str,
        username=report.user.username if report.user else None,
        user_full_name=report.user.full_name if report.user else None,
        vertical_id=report.vertical_id,
        vertical_name=report.vertical.name if report.vertical else None,
        report_date=report.report_date,
        work_summary=report.work_summary,
        tasks_completed=report.tasks_completed,
        tasks=tasks_list,
        blockers=report.blockers,
        issues=report.issues,
        next_actions=report.next_actions,
        evidence_links=report.evidence_links,
        status=report.status,
        reviewer_id=report.reviewer_id,
        reviewer_username=report.reviewer.username if report.reviewer else None,
        reviewed_by_id=report.reviewed_by_id,
        reviewed_by_username=report.reviewed_by.username if report.reviewed_by else None,
        review_comments=report.review_comments,
        history=history_list,
        submitted_at=report.submitted_at,
        reviewed_at=report.reviewed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _format_weekly_report_response(report, db: Optional[Session] = None) -> WeeklyReportResponse:
    """Helper to convert weekly report model to response schema with 7-day breakdown."""
    user_role_str = None
    daily_responses: List[DailyReportResponse] = []
    days_reported: List[Dict[str, Any]] = []
    tasks_worked_on: List[DailyReportTaskResponse] = []

    if db and report.user_id:
        auth = AuthorityService(db)
        roles = auth.get_user_role_names(report.user_id)
        user_role_str = list(roles)[0] if roles else None

        # Fetch daily reports within this 7-day week
        daily_stmt = (
            select(DailyWorkReport)
            .options(
                selectinload(DailyWorkReport.user),
                selectinload(DailyWorkReport.vertical),
                selectinload(DailyWorkReport.reviewer),
                selectinload(DailyWorkReport.reviewed_by),
                selectinload(DailyWorkReport.report_tasks).selectinload(DailyReportTask.task),
                selectinload(DailyWorkReport.history_entries).selectinload(DailyReportHistory.actor),
            )
            .where(
                DailyWorkReport.user_id == report.user_id,
                DailyWorkReport.report_date >= report.week_start_date,
                DailyWorkReport.report_date <= report.week_end_date,
            )
            .order_by(DailyWorkReport.report_date.asc())
        )
        daily_list = list(db.scalars(daily_stmt).all())
        daily_responses = [_format_daily_report_response(dr, db) for dr in daily_list]

        # Map by report_date
        daily_by_date = {dr.report_date: dr for dr in daily_list}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i in range(7):
            cur_date = report.week_start_date + timedelta(days=i)
            cur_dr = daily_by_date.get(cur_date)
            day_entry = {
                "date": cur_date.isoformat(),
                "day_of_week": day_names[i],
                "reported": cur_dr is not None,
                "report_id": str(cur_dr.id) if cur_dr else None,
                "status": cur_dr.status.value if cur_dr else None,
            }
            days_reported.append(day_entry)

        # Collect unique tasks worked on
        seen_task_ids = set()
        for dr in daily_list:
            for rt in dr.report_tasks:
                if rt.task_id and rt.task_id not in seen_task_ids:
                    seen_task_ids.add(rt.task_id)
                    tasks_worked_on.append(
                        DailyReportTaskResponse(
                            task_id=rt.task_id,
                            task_title=rt.task.title if rt.task else "Task",
                            task_status=rt.task.status.value if rt.task else "ASSIGNED",
                            progress_notes=rt.progress_notes,
                        )
                    )

    return WeeklyReportResponse(
        id=report.id,
        user_id=report.user_id,
        author_id=report.user_id,
        user_role=user_role_str,
        username=report.user.username if report.user else None,
        user_full_name=report.user.full_name if report.user else None,
        vertical_id=report.vertical_id,
        vertical_name=report.vertical.name if report.vertical else None,
        week_start_date=report.week_start_date,
        week_end_date=report.week_end_date,
        days_reported_count=len(daily_responses),
        days_reported=days_reported,
        summary=report.summary,
        completed_work=report.completed_work,
        outstanding_work=report.outstanding_work,
        tasks_worked_on=tasks_worked_on,
        daily_reports=daily_responses,
        blockers=report.blockers,
        issues=report.issues,
        priorities_next_week=report.priorities_next_week,
        supervisor_comments=report.supervisor_comments,
        reviewer_id=report.reviewer_id,
        reviewer_username=report.reviewer.username if report.reviewer else None,
        reviewed_by_id=report.reviewed_by_id,
        reviewed_by_username=report.reviewed_by.username if report.reviewed_by else None,
        status=report.status,
        submitted_at=report.submitted_at,
        reviewed_at=report.reviewed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


# -----------------------------------------------------------------------------
# Daily Work Reports
# -----------------------------------------------------------------------------

@reports_router.get("/daily", response_model=DailyReportListResponse)
async def list_daily_reports(
    user_id: Optional[uuid.UUID] = Query(None),
    vertical_id: Optional[uuid.UUID] = Query(None),
    status: Optional[DailyReportStatus] = Query(None),
    report_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists daily work reports within authorized scope and retention window."""
    service = ReportService(db)
    items, total = service.list_daily_reports(
        current_user=current_user,
        user_id=user_id,
        vertical_id=vertical_id,
        status=status,
        report_date=report_date,
        skip=skip,
        limit=limit,
    )
    return DailyReportListResponse(
        total=total,
        items=[_format_daily_report_response(r, db) for r in items],
    )


@reports_router.get("/review-queue", response_model=DailyReportListResponse)
async def get_review_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves pending daily reports authorized for review by the current user."""
    service = ReportService(db)
    items, total = service.get_supervisor_review_queue(
        current_user=current_user,
        skip=skip,
        limit=limit,
    )
    return DailyReportListResponse(
        total=total,
        items=[_format_daily_report_response(r, db) for r in items],
    )


@reports_router.post("/daily", response_model=DailyReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_daily_report(
    data: DailyReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates and submits a daily work report for the authenticated user."""
    service = ReportService(db)
    report = service.create_daily_report(data, user_id=current_user.id)
    db.commit()
    refreshed = service.get_daily_report_by_id(report.id, current_user=current_user)
    return _format_daily_report_response(refreshed, db)


@reports_router.get("/daily/{id}", response_model=DailyReportResponse)
async def get_daily_report(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single daily work report with authorization check."""
    service = ReportService(db)
    report = service.get_daily_report_by_id(id, current_user=current_user)
    return _format_daily_report_response(report, db)


@reports_router.put("/daily/{id}", response_model=DailyReportResponse)
async def update_daily_report(
    id: uuid.UUID,
    data: DailyReportUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates/resubmits a returned or draft daily work report."""
    service = ReportService(db)
    report = service.resubmit_daily_report(id, data=data, actor_id=current_user.id)
    db.commit()
    refreshed = service.get_daily_report_by_id(report.id, current_user=current_user)
    return _format_daily_report_response(refreshed, db)


@reports_router.post("/daily/{id}/resubmit", response_model=DailyReportResponse)
async def resubmit_daily_report(
    id: uuid.UUID,
    data: DailyReportUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly resubmits a returned report with corrections."""
    service = ReportService(db)
    report = service.resubmit_daily_report(id, data=data, actor_id=current_user.id)
    db.commit()
    refreshed = service.get_daily_report_by_id(report.id, current_user=current_user)
    return _format_daily_report_response(refreshed, db)


@reports_router.post("/daily/{id}/review", response_model=DailyReportResponse)
async def review_daily_report(
    id: uuid.UUID,
    data: DailyReportReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Applies supervisor review (Approve or Return) under exact hierarchical rules."""
    service = ReportService(db)
    report = service.review_daily_report(id, reviewer=current_user, data=data)
    db.commit()
    refreshed = service.get_daily_report_by_id(report.id, current_user=current_user)
    return _format_daily_report_response(refreshed, db)


# -----------------------------------------------------------------------------
# Weekly Reports & Dynamic Rollup
# -----------------------------------------------------------------------------

@reports_router.get("/weekly/current", response_model=WeeklyReportResponse)
async def get_current_weekly_report(
    user_id: Optional[uuid.UUID] = Query(None),
    week_start: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Automatically retrieves or generates a 7-day weekly report from daily reports.
    Defaults to current week start (Monday) and current user.
    """
    service = ReportService(db)
    target_uid = user_id or current_user.id

    if target_uid != current_user.id and not service.can_user_view_user_reports(current_user, target_uid):
        raise ForbiddenException("Access denied: You are not authorized to view this user's weekly reports")

    if week_start:
        target_start = week_start
    else:
        today = date.today()
        # Monday of current week
        target_start = today - timedelta(days=today.weekday())

    report = service.get_or_generate_weekly_report(target_uid, target_start)
    db.commit()
    refreshed = service.get_weekly_report_by_id(report.id, current_user=current_user)
    return _format_weekly_report_response(refreshed, db)


@reports_router.get("/weekly/rollup", response_model=WeeklyRollupResponse)
async def get_weekly_rollup(
    start_date: date = Query(...),
    end_date: date = Query(...),
    vertical_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dynamically aggregates operational activity across Daily Reports, Tasks, and Issues."""
    service = ReportService(db)
    return service.generate_weekly_rollup(
        start_date=start_date,
        end_date=end_date,
        vertical_id=vertical_id,
        user_id=user_id,
    )


@reports_router.get("/weekly", response_model=WeeklyReportListResponse)
async def list_weekly_reports(
    user_id: Optional[uuid.UUID] = Query(None),
    vertical_id: Optional[uuid.UUID] = Query(None),
    status: Optional[WeeklyReportStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists weekly operational reports within authorized scope."""
    service = ReportService(db)
    items, total = service.list_weekly_reports(
        current_user=current_user,
        user_id=user_id,
        vertical_id=vertical_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return WeeklyReportListResponse(
        total=total,
        items=[_format_weekly_report_response(r, db) for r in items],
    )


@reports_router.post("/weekly", response_model=WeeklyReportResponse, status_code=status.HTTP_201_CREATED)
async def create_weekly_report(
    data: WeeklyReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a weekly operational report."""
    service = ReportService(db)
    report = service.create_weekly_report(data, user_id=current_user.id)
    db.commit()
    refreshed = service.get_weekly_report_by_id(report.id, current_user=current_user)
    return _format_weekly_report_response(refreshed, db)


@reports_router.get("/weekly/{id}", response_model=WeeklyReportResponse)
async def get_weekly_report(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single weekly report."""
    service = ReportService(db)
    report = service.get_weekly_report_by_id(id, current_user=current_user)
    return _format_weekly_report_response(report, db)


@reports_router.post("/weekly/{id}/review", response_model=WeeklyReportResponse)
async def review_weekly_report(
    id: uuid.UUID,
    data: WeeklyReportReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Applies supervisor review to a weekly report."""
    service = ReportService(db)
    report = service.review_weekly_report(id, reviewer=current_user, data=data)
    db.commit()
    refreshed = service.get_weekly_report_by_id(report.id, current_user=current_user)
    return _format_weekly_report_response(refreshed, db)
