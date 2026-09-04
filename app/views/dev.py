"""
Jinja2 Development Interface Views
Minimal, clean HTML views used ONLY for backend foundation, security, operational, event coordination,
communication, governance & analytics verification.
"""

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Form, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.health import get_app_health, get_database_health
from app.models.calendar import ActivityCategory, CalendarAudience, CalendarPriority, CalendarStatus, DeadlineType
from app.models.communication import (
    AcknowledgementStatus,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    CommunicationLogStatus,
    CommunicationType,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
    NotificationReadStatus,
    NotificationType,
)
from app.models.event import EventMemberRole, EventMemberStatus, EventStatus, EventType, ReadinessCategory, ReadinessStatus
from app.models.form import FormAudience, FormFieldType, FormStatus, FormSubmissionStatus
from app.models.governance import (
    ConfigValueType,
    OwnershipTransfer,
    SystemConfig,
    TransferResourceType,
    TransferStatus,
)
from app.models.issue import IssueSensitivity, IssueStatus
from app.models.meeting import MeetingStatus, MeetingType, RSVPStatus
from app.models.organization import VerticalStatus
from app.models.report import DailyReportStatus, WeeklyReportStatus
from app.models.requirement import RequirementPriority, RequirementStatus
from app.models.task import TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus
from app.schemas.analytics import AdminReportResponse
from app.schemas.calendar import CalendarCreate
from app.schemas.communication import (
    AnnouncementCreate,
    AnnouncementUpdate,
    CommunicationLogCreate,
    DirectiveAcknowledgeRequest,
    DirectiveCreate,
    DirectiveUpdate,
)
from app.schemas.event import EventCreate, EventMemberCreate, EventReadinessUpdate, EventTransitionRequest
from app.schemas.form import FormCreate, FormFieldSchema, FormSubmissionCreate, FormSubmissionReviewRequest, FormTransformationConfig
from app.schemas.governance import (
    OwnershipTransferCreate,
    OwnershipTransferReviewRequest,
    SystemConfigCreate,
    SystemConfigUpdate,
)
from app.schemas.issue import IssueCreate, IssueEscalateRequest, IssueTransitionRequest
from app.schemas.meeting import MeetingCreate, MeetingRescheduleRequest, MeetingRSVPRequest
from app.schemas.organization import VerticalCreate
from app.schemas.report import DailyReportCreate, DailyReportReviewRequest, WeeklyReportCreate
from app.schemas.requirement import RequirementCreate, RequirementMessageCreate, RequirementTransitionRequest
from app.schemas.task import TaskAssignRequest, TaskCommentCreate, TaskCreate, TaskTransitionRequest, TaskUpdate
from app.schemas.test_record import SystemTestRecordCreate
from app.schemas.user import UserCreate
from app.services.admin_reporting_service import AdminReportingService
from app.services.analytics_service import AnalyticsService
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.communication_service import CommunicationLogService
from app.services.config_service import SystemConfigService
from app.services.directive_service import DirectiveService
from app.services.event_service import EventService
from app.services.form_service import FormService
from app.services.issue_service import IssueService
from app.services.meeting_service import MeetingService
from app.services.notification_service import NotificationService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService
from app.services.report_service import ReportService
from app.services.requirement_service import RequirementService
from app.services.task_service import TaskService
from app.services.test_record_service import SystemTestRecordService
from app.services.transfer_service import OwnershipTransferService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService

settings = get_settings()
templates = Jinja2Templates(directory="templates")
dev_router = APIRouter(prefix="/dev", tags=["Development Interface"])


def get_current_dev_user(request: Request, db: Session):
    """Helper to extract user from dev session cookie if logged in."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        auth_service = AuthService(db)
        user, _ = auth_service.validate_session(token)
        return user
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Core & Foundation Views
# -----------------------------------------------------------------------------

@dev_router.get("", response_class=HTMLResponse)
async def dev_index(request: Request, db: Session = Depends(get_db)):
    """Dev Interface Overview Page"""
    app_health = get_app_health()
    db_health = get_database_health()
    current_user = get_current_dev_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="dev_index.html",
        context={
            "title": "Development Verification Dashboard",
            "app_health": app_health,
            "db_health": db_health,
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "current_user": current_user,
        },
    )


@dev_router.get("/database", response_class=HTMLResponse)
async def dev_database(request: Request, db: Session = Depends(get_db)):
    """PostgreSQL Database Live Health Verification Page"""
    db_health = get_database_health()
    current_user = get_current_dev_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="dev_database.html",
        context={
            "title": "PostgreSQL Health & Connection Status",
            "db_health": db_health,
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            "current_user": current_user,
        },
    )


@dev_router.get("/test-records", response_class=HTMLResponse)
async def dev_test_records_list(
    request: Request,
    created_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Test Records List & Creation Form (Phase 1 entity)"""
    service = SystemTestRecordService(db)
    records = service.list_all()
    total = service.count()
    current_user = get_current_dev_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="dev_test_records.html",
        context={
            "title": "System Test Records Verification",
            "records": records,
            "total": total,
            "created_id": created_id,
            "current_user": current_user,
        },
    )


@dev_router.post("/test-records", response_class=HTMLResponse)
async def dev_create_test_record(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Handles test record form submission with explicit transaction commit."""
    try:
        service = SystemTestRecordService(db)
        payload = SystemTestRecordCreate(name=name, description=description)
        new_record = service.create(payload)
        return RedirectResponse(
            url=f"/dev/test-records?created_id={new_record.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        records = SystemTestRecordService(db).list_all()
        current_user = get_current_dev_user(request, db)
        return templates.TemplateResponse(
            request=request,
            name="dev_test_records.html",
            context={
                "title": "System Test Records Verification",
                "records": records,
                "total": len(records),
                "error": str(exc),
                "current_user": current_user,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# -----------------------------------------------------------------------------
# Phase 2: Auth, Users, Org, Security Views
# -----------------------------------------------------------------------------

@dev_router.get("/auth", response_class=HTMLResponse)
async def dev_auth_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Auth & Session verification page."""
    current_user = get_current_dev_user(request, db)
    roles = []
    effective_perms = []
    verticals = []
    if current_user:
        rbac = RbacService(db)
        org = OrganizationService(db)
        roles = rbac.get_user_roles(current_user.id)
        effective_perms = sorted(list(rbac.get_effective_permissions(current_user.id)))
        verticals = org.get_user_verticals(current_user.id)

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)

    return templates.TemplateResponse(
        request=request,
        name="dev_auth.html",
        context={
            "title": "Authentication & Sessions Verification",
            "current_user": current_user,
            "roles": roles,
            "effective_permissions": effective_perms,
            "verticals": verticals,
            "token": token,
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/auth/login", response_class=HTMLResponse)
async def dev_auth_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handles login form submission."""
    try:
        auth_service = AuthService(db)
        ip = request.client.host if request.client else None
        user, session, raw_token = auth_service.login(username=username, password=password, ip_address=ip)
        db.commit()

        redirect = RedirectResponse(url="/dev/auth?message=Login+successful", status_code=status.HTTP_303_SEE_OTHER)
        redirect.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=raw_token,
            httponly=settings.SESSION_COOKIE_HTTPONLY,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=settings.SESSION_EXPIRE_HOURS * 3600,
        )
        return redirect
    except Exception as exc:
        return RedirectResponse(url=f"/dev/auth?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/auth/logout", response_class=HTMLResponse)
async def dev_auth_logout(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handles logout form submission."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        auth_service = AuthService(db)
        auth_service.logout(token)
        db.commit()

    redirect = RedirectResponse(url="/dev/auth?message=Logged+out+successfully", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(settings.SESSION_COOKIE_NAME)
    return redirect


@dev_router.get("/users", response_class=HTMLResponse)
async def dev_users_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """User Management verification page."""
    current_user = get_current_dev_user(request, db)
    user_service = UserService(db)
    rbac_service = RbacService(db)
    org_service = OrganizationService(db)

    users = user_service.list_users(limit=100)
    roles = rbac_service.list_roles()
    verticals = org_service.list_verticals()

    user_data = []
    for u in users:
        u_roles = rbac_service.get_user_roles(u.id)
        u_verts = org_service.get_user_verticals(u.id)
        user_data.append({
            "user": u,
            "roles": u_roles,
            "verticals": u_verts,
        })

    return templates.TemplateResponse(
        request=request,
        name="dev_users.html",
        context={
            "title": "User Management & Lifecycle Verification",
            "current_user": current_user,
            "users": user_data,
            "available_roles": roles,
            "available_verticals": verticals,
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/users/create", response_class=HTMLResponse)
async def dev_create_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    email: Optional[str] = Form(None),
    password: str = Form(...),
    role_id: Optional[str] = Form(None),
    vertical_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Handles user creation from dev interface."""
    try:
        user_service = UserService(db)
        actor = get_current_dev_user(request, db)
        actor_id = actor.id if actor else None

        role_ids = [UUID(role_id)] if role_id else []
        vertical_ids = [UUID(vertical_id)] if vertical_id else []

        payload = UserCreate(
            username=username,
            full_name=full_name,
            email=email if email else None,
            password=password,
            role_ids=role_ids,
            vertical_ids=vertical_ids,
        )
        new_u = user_service.create_user(data=payload, actor_id=actor_id)
        db.commit()
        return RedirectResponse(
            url=f"/dev/users?message=User+{new_u.username}+created+successfully",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        return RedirectResponse(url=f"/dev/users?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/users/{user_id}/toggle-status", response_class=HTMLResponse)
async def dev_toggle_user_status(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """Toggles user account status between ACTIVE and DISABLED."""
    try:
        user_service = UserService(db)
        actor = get_current_dev_user(request, db)
        actor_id = actor.id if actor else None
        target_u = user_service.get_user_by_id(user_id)

        if target_u.account_status == AccountStatus.ACTIVE:
            user_service.disable_user(user_id, actor_id=actor_id)
            msg = f"User+{target_u.username}+disabled"
        else:
            user_service.enable_user(user_id, actor_id=actor_id)
            msg = f"User+{target_u.username}+enabled"

        db.commit()
        return RedirectResponse(url=f"/dev/users?message={msg}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/users?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/organization", response_class=HTMLResponse)
async def dev_organization_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Organization & Verticals verification page."""
    current_user = get_current_dev_user(request, db)
    org_service = OrganizationService(db)
    org = org_service.get_organization()
    verticals = org_service.list_verticals(org.id)

    return templates.TemplateResponse(
        request=request,
        name="dev_organization.html",
        context={
            "title": "Organization & Verticals Verification",
            "current_user": current_user,
            "organization": org,
            "verticals": verticals,
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/organization/verticals", response_class=HTMLResponse)
async def dev_create_vertical(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates a new vertical from dev interface."""
    try:
        org_service = OrganizationService(db)
        audit_service = AuditService(db)
        actor = get_current_dev_user(request, db)
        actor_id = actor.id if actor else None

        v = org_service.create_vertical(VerticalCreate(name=name, description=description))
        audit_service.log(
            action="VERTICAL_CREATE",
            resource_type="VERTICAL",
            resource_id=str(v.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"name": v.name},
        )
        db.commit()
        return RedirectResponse(
            url=f"/dev/organization?message=Vertical+{v.name}+created",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        return RedirectResponse(url=f"/dev/organization?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/security", response_class=HTMLResponse)
async def dev_security_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Security verification and audit logs viewer."""
    current_user = get_current_dev_user(request, db)
    audit_service = AuditService(db)
    rbac_service = RbacService(db)

    recent_logs = audit_service.list_logs(limit=50)
    roles = rbac_service.list_roles()
    permissions = rbac_service.list_permissions()

    return templates.TemplateResponse(
        request=request,
        name="dev_security.html",
        context={
            "title": "Security, RBAC & Audit Verification",
            "current_user": current_user,
            "audit_logs": recent_logs,
            "roles": roles,
            "permissions": permissions,
        },
    )


# -----------------------------------------------------------------------------
# Phase 3: Master Tasks, Calendar, Issues, Reports
# -----------------------------------------------------------------------------

@dev_router.get("/tasks", response_class=HTMLResponse)
async def dev_tasks_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Master Tasks verification page."""
    current_user = get_current_dev_user(request, db)
    task_service = TaskService(db)
    org_service = OrganizationService(db)
    user_service = UserService(db)

    tasks, total = task_service.list_tasks(limit=100)
    verticals = org_service.list_verticals()
    users = user_service.list_users(limit=100)

    return templates.TemplateResponse(
        request=request,
        name="dev_tasks.html",
        context={
            "title": "Master Tasks System",
            "current_user": current_user,
            "tasks": tasks,
            "total": total,
            "verticals": verticals,
            "users": users,
            "task_types": list(TaskType),
            "task_priorities": list(TaskPriority),
            "task_statuses": list(TaskStatus),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/tasks/create", response_class=HTMLResponse)
async def dev_create_task(
    request: Request,
    vertical_id: UUID = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    task_type: TaskType = Form(TaskType.ROUTINE),
    priority: TaskPriority = Form(TaskPriority.MEDIUM),
    assigned_to_id: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates a task from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        task_service = TaskService(db)
        assignee_uuid = UUID(assigned_to_id) if assigned_to_id else None
        deadline_dt = datetime.fromisoformat(deadline) if deadline else None

        payload = TaskCreate(
            vertical_id=vertical_id,
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            assigned_to_id=assignee_uuid,
            deadline=deadline_dt,
        )
        task = task_service.create_task(payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/tasks?message=Task+{task.title}+created", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/tasks?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/tasks/{task_id}/transition", response_class=HTMLResponse)
async def dev_transition_task(
    task_id: UUID,
    request: Request,
    status_val: TaskStatus = Form(..., alias="status"),
    completion_percentage: Optional[int] = Form(None),
    blockers: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Transitions task status from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        task_service = TaskService(db)
        payload = TaskTransitionRequest(
            status=status_val,
            completion_percentage=completion_percentage,
            blockers=blockers,
            remarks=remarks,
        )
        task = task_service.transition_status(task_id, payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/tasks?message=Task+status+changed+to+{task.status.value}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/tasks?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/my-work", response_class=HTMLResponse)
async def dev_my_work_page(
    request: Request,
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Unified My Work operational dashboard view."""
    current_user = get_current_dev_user(request, db)
    my_work = None
    if current_user:
        my_work = WorkspaceService.get_unified_my_work(db, current_user)

    return templates.TemplateResponse(
        request=request,
        name="dev_my_work.html",
        context={
            "title": "Unified My Work - Operational Workspace",
            "current_user": current_user,
            "my_work": my_work,
            "status_filter": status_filter,
        },
    )


@dev_router.get("/calendar", response_class=HTMLResponse)
async def dev_calendar_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Master Calendar verification page."""
    current_user = get_current_dev_user(request, db)
    calendar_service = CalendarService(db)
    org_service = OrganizationService(db)

    entries, total = calendar_service.list_entries(user=current_user, limit=100)
    verticals = org_service.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_calendar.html",
        context={
            "title": "Master Calendar Activities",
            "current_user": current_user,
            "entries": entries,
            "total": total,
            "verticals": verticals,
            "categories": list(ActivityCategory),
            "priorities": list(CalendarPriority),
            "audiences": list(CalendarAudience),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/calendar/create", response_class=HTMLResponse)
async def dev_create_calendar_entry(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    activity_date: str = Form(...),
    category: ActivityCategory = Form(ActivityCategory.ACTIVITY),
    priority: CalendarPriority = Form(CalendarPriority.MEDIUM),
    deadline_type: DeadlineType = Form(DeadlineType.INFORMATIONAL),
    audience: CalendarAudience = Form(CalendarAudience.ORGANIZATION),
    vertical_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates calendar entry from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        calendar_service = CalendarService(db)
        vert_uuid = UUID(vertical_id) if vertical_id else None
        act_date = date.fromisoformat(activity_date)

        payload = CalendarCreate(
            title=title,
            description=description,
            activity_date=act_date,
            category=category,
            priority=priority,
            deadline_type=deadline_type,
            audience=audience,
            vertical_id=vert_uuid,
        )
        entry = calendar_service.create_entry(payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/calendar?message=Calendar+entry+{entry.title}+created", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/calendar?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/issues", response_class=HTMLResponse)
async def dev_issues_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Issue & Escalation Register verification page."""
    current_user = get_current_dev_user(request, db)
    issue_service = IssueService(db)
    org_service = OrganizationService(db)
    user_service = UserService(db)

    issues = []
    total = 0
    if current_user:
        issues, total = issue_service.list_issues(current_user=current_user, limit=100)

    verticals = org_service.list_verticals()
    users = user_service.list_users(limit=100)

    return templates.TemplateResponse(
        request=request,
        name="dev_issues.html",
        context={
            "title": "Issue & Escalation Register",
            "current_user": current_user,
            "issues": issues,
            "total": total,
            "verticals": verticals,
            "users": users,
            "sensitivities": list(IssueSensitivity),
            "statuses": list(IssueStatus),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/issues/create", response_class=HTMLResponse)
async def dev_create_issue(
    request: Request,
    vertical_id: UUID = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    sensitivity: IssueSensitivity = Form(IssueSensitivity.NORMAL),
    action_required: Optional[str] = Form(None),
    assigned_to_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Raises an issue from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        issue_service = IssueService(db)
        assignee_uuid = UUID(assigned_to_id) if assigned_to_id else None

        payload = IssueCreate(
            vertical_id=vertical_id,
            title=title,
            description=description,
            sensitivity=sensitivity,
            action_required=action_required,
            assigned_to_id=assignee_uuid,
        )
        issue = issue_service.create_issue(payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/issues?message=Issue+{issue.title}+raised", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/issues?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/reports", response_class=HTMLResponse)
async def dev_reports_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Daily & Weekly Reports verification page."""
    current_user = get_current_dev_user(request, db)
    report_service = ReportService(db)
    org_service = OrganizationService(db)

    daily_reports = []
    weekly_reports = []
    if current_user:
        daily_reports, _ = report_service.list_daily_reports(current_user=current_user, limit=50)
        weekly_reports, _ = report_service.list_weekly_reports(current_user=current_user, limit=50)

    verticals = org_service.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_reports.html",
        context={
            "title": "Daily & Weekly Work Reports",
            "current_user": current_user,
            "daily_reports": daily_reports,
            "weekly_reports": weekly_reports,
            "verticals": verticals,
            "today": date.today().isoformat(),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/reports/daily/submit", response_class=HTMLResponse)
async def dev_submit_daily_report(
    request: Request,
    vertical_id: UUID = Form(...),
    report_date: str = Form(...),
    work_summary: str = Form(...),
    tasks_completed: Optional[str] = Form(None),
    blockers: Optional[str] = Form(None),
    next_actions: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Submits daily work report from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        report_service = ReportService(db)
        rep_date = date.fromisoformat(report_date)

        payload = DailyReportCreate(
            vertical_id=vertical_id,
            report_date=rep_date,
            work_summary=work_summary,
            tasks_completed=tasks_completed,
            blockers=blockers,
            next_actions=next_actions,
            submit_now=True,
        )
        report = report_service.create_daily_report(payload, user_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/reports?message=Daily+report+submitted+for+{report.report_date}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/reports?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


# -----------------------------------------------------------------------------
# Phase 4: Events, Requirements, Meetings, Forms
# -----------------------------------------------------------------------------

@dev_router.get("/events", response_class=HTMLResponse)
async def dev_events_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Events & Readiness verification page."""
    current_user = get_current_dev_user(request, db)
    event_service = EventService(db)
    org_service = OrganizationService(db)
    user_service = UserService(db)

    events, total = event_service.list_events(limit=100)
    verticals = org_service.list_verticals()
    users = user_service.list_users(limit=100)

    return templates.TemplateResponse(
        request=request,
        name="dev_events.html",
        context={
            "title": "Events & Readiness System",
            "current_user": current_user,
            "events": events,
            "total": total,
            "verticals": verticals,
            "users": users,
            "event_types": list(EventType),
            "event_statuses": list(EventStatus),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/events/create", response_class=HTMLResponse)
async def dev_create_event(
    request: Request,
    vertical_id: UUID = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    event_type: EventType = Form(EventType.TOURNAMENT),
    planned_date: str = Form(...),
    location: Optional[str] = Form(None),
    society_name: Optional[str] = Form(None),
    event_head_id: Optional[str] = Form(None),
    primary_poc_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates event from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        event_service = EventService(db)
        p_date = date.fromisoformat(planned_date)
        head_uuid = UUID(event_head_id) if event_head_id else None
        poc_uuid = UUID(primary_poc_id) if primary_poc_id else None

        payload = EventCreate(
            vertical_id=vertical_id,
            name=name,
            description=description,
            event_type=event_type,
            planned_date=p_date,
            location=location,
            society_name=society_name,
            event_head_id=head_uuid,
            primary_poc_id=poc_uuid,
        )
        event = event_service.create_event(payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/events?message=Event+{event.name}+created", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/events?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/requirements", response_class=HTMLResponse)
async def dev_requirements_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Cross-Vertical Requirements verification page."""
    current_user = get_current_dev_user(request, db)
    req_service = RequirementService(db)
    org_service = OrganizationService(db)
    user_service = UserService(db)

    reqs, total = req_service.list_requirements(limit=100)
    verticals = org_service.list_verticals()
    users = user_service.list_users(limit=100)

    return templates.TemplateResponse(
        request=request,
        name="dev_requirements.html",
        context={
            "title": "Cross-Vertical Requirements",
            "current_user": current_user,
            "requirements": reqs,
            "total": total,
            "verticals": verticals,
            "users": users,
            "priorities": list(RequirementPriority),
            "statuses": list(RequirementStatus),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/requirements/create", response_class=HTMLResponse)
async def dev_create_requirement(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    requesting_vertical_id: UUID = Form(...),
    target_vertical_id: UUID = Form(...),
    priority: RequirementPriority = Form(RequirementPriority.MEDIUM),
    assignee_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates a requirement from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        req_service = RequirementService(db)
        assignee_uuid = UUID(assignee_id) if assignee_id else None

        payload = RequirementCreate(
            title=title,
            description=description,
            requesting_vertical_id=requesting_vertical_id,
            target_vertical_id=target_vertical_id,
            priority=priority,
            assignee_id=assignee_uuid,
        )
        req = req_service.create_requirement(payload, requester_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/requirements?message=Requirement+{req.title}+created", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/requirements?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/meetings", response_class=HTMLResponse)
async def dev_meetings_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Meetings & RSVPs verification page."""
    current_user = get_current_dev_user(request, db)
    meeting_service = MeetingService(db)
    org_service = OrganizationService(db)
    event_service = EventService(db)

    meetings, total = meeting_service.list_meetings(limit=100)
    verticals = org_service.list_verticals()
    events, _ = event_service.list_events(limit=50)

    return templates.TemplateResponse(
        request=request,
        name="dev_meetings.html",
        context={
            "title": "Operational Meetings & RSVPs",
            "current_user": current_user,
            "meetings": meetings,
            "total": total,
            "verticals": verticals,
            "events": events,
            "meeting_types": list(MeetingType),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/meetings/create", response_class=HTMLResponse)
async def dev_create_meeting(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    meeting_type: MeetingType = Form(MeetingType.INTERNAL_SYNC),
    meeting_date: str = Form(...),
    location: Optional[str] = Form(None),
    vertical_id: Optional[str] = Form(None),
    event_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Schedules a meeting from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        meeting_service = MeetingService(db)
        m_date = date.fromisoformat(meeting_date)
        vert_uuid = UUID(vertical_id) if vertical_id else None
        ev_uuid = UUID(event_id) if event_id else None

        payload = MeetingCreate(
            title=title,
            description=description,
            meeting_type=meeting_type,
            meeting_date=m_date,
            location=location,
            vertical_id=vert_uuid,
            event_id=ev_uuid,
        )
        meeting = meeting_service.create_meeting(payload, organizer_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/meetings?message=Meeting+{meeting.title}+scheduled", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/meetings?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/forms", response_class=HTMLResponse)
async def dev_forms_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Advanced Forms & Submissions verification page."""
    current_user = get_current_dev_user(request, db)
    form_service = FormService(db)
    org_service = OrganizationService(db)

    forms, total = form_service.list_forms(limit=100)
    submissions, sub_total = form_service.list_submissions(limit=50)
    verticals = org_service.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_forms.html",
        context={
            "title": "Advanced Forms & Submissions",
            "current_user": current_user,
            "forms": forms,
            "total": total,
            "submissions": submissions,
            "sub_total": sub_total,
            "verticals": verticals,
            "audiences": list(FormAudience),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/forms/create", response_class=HTMLResponse)
async def dev_create_form(
    request: Request,
    name: str = Form(...),
    purpose: str = Form(...),
    description: Optional[str] = Form(None),
    target_audience: FormAudience = Form(FormAudience.ORGANIZATION),
    vertical_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates form with default sample schema from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        form_service = FormService(db)
        vert_uuid = UUID(vertical_id) if vertical_id else None

        sample_fields = [
            FormFieldSchema(key="title", label="Request Title", type=FormFieldType.TEXT, required=True),
            FormFieldSchema(key="details", label="Additional Operational Details", type=FormFieldType.LONG_TEXT, required=False),
        ]
        sample_trans = FormTransformationConfig(
            target_entity="TASK",
            field_mappings={"title": "title", "description": "details"},
        )

        payload = FormCreate(
            name=name,
            purpose=purpose,
            description=description,
            target_audience=target_audience,
            vertical_id=vert_uuid,
            initial_schema=sample_fields,
            transformation_config=sample_trans,
        )
        form = form_service.create_form(payload, owner_id=actor.id)
        form_service.publish_form_version(form.id, version_number=1, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/forms?message=Form+{form.name}+created+and+published+as+v1", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/forms?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


# -----------------------------------------------------------------------------
# Phase 5: Announcements, Directives, Notifications, Governance & Analytics
# -----------------------------------------------------------------------------

@dev_router.get("/announcements", response_class=HTMLResponse)
async def dev_announcements_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Announcements verification page."""
    current_user = get_current_dev_user(request, db)
    service = AnnouncementService(db)
    rbac = RbacService(db)
    org = OrganizationService(db)

    user_roles = {r.name for r in rbac.get_user_roles(current_user.id)} if current_user else set()
    is_admin = "ADMIN" in user_roles or "SPORTS_CORE" in user_roles
    user_verticals = [v.id for v, _ in org.get_user_verticals(current_user.id)] if current_user else []

    announcements = []
    total = 0
    if current_user:
        announcements, total = service.list_announcements(
            current_user=current_user,
            user_vertical_ids=user_verticals,
            is_admin=is_admin,
            limit=100,
        )

    verticals = org_service.list_verticals() if (org_service := OrganizationService(db)) else []

    return templates.TemplateResponse(
        request=request,
        name="dev_announcements.html",
        context={
            "title": "Announcements & Broadcasts",
            "current_user": current_user,
            "announcements": announcements,
            "total": total,
            "verticals": verticals,
            "priorities": list(AnnouncementPriority),
            "scopes": list(AnnouncementScope),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/announcements/create", response_class=HTMLResponse)
async def dev_create_announcement(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form("GENERAL"),
    priority: AnnouncementPriority = Form(AnnouncementPriority.NORMAL),
    scope: AnnouncementScope = Form(AnnouncementScope.ALL),
    vertical_id: Optional[str] = Form(None),
    publish_now: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Creates announcement from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = AnnouncementService(db)
        vert_uuid = UUID(vertical_id) if vertical_id else None

        payload = AnnouncementCreate(
            title=title,
            content=content,
            category=category,
            priority=priority,
            scope=scope,
            vertical_id=vert_uuid,
            publish_now=publish_now,
        )
        ann = service.create_announcement(payload, author_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/announcements?message=Announcement+{ann.title}+published", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/announcements?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/directives", response_class=HTMLResponse)
async def dev_directives_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Directives & Compliance verification page."""
    current_user = get_current_dev_user(request, db)
    service = DirectiveService(db)
    rbac = RbacService(db)
    org = OrganizationService(db)

    user_roles = {r.name for r in rbac.get_user_roles(current_user.id)} if current_user else set()
    is_admin = "ADMIN" in user_roles or "SPORTS_CORE" in user_roles
    user_verticals = [v.id for v, _ in org.get_user_verticals(current_user.id)] if current_user else []

    directives = []
    total = 0
    if current_user:
        directives, total = service.list_directives(
            current_user=current_user,
            user_vertical_ids=user_verticals,
            is_admin=is_admin,
            limit=100,
        )

    verticals = org.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_directives.html",
        context={
            "title": "Operational Directives & Compliance",
            "current_user": current_user,
            "directives": directives,
            "total": total,
            "verticals": verticals,
            "priorities": list(DirectivePriority),
            "scopes": list(DirectiveScope),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/directives/create", response_class=HTMLResponse)
async def dev_create_directive(
    request: Request,
    title: str = Form(...),
    instruction: str = Form(...),
    priority: DirectivePriority = Form(DirectivePriority.MEDIUM),
    scope: DirectiveScope = Form(DirectiveScope.ALL),
    vertical_id: Optional[str] = Form(None),
    issue_now: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Creates directive from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = DirectiveService(db)
        vert_uuid = UUID(vertical_id) if vertical_id else None

        payload = DirectiveCreate(
            title=title,
            instruction=instruction,
            priority=priority,
            scope=scope,
            vertical_id=vert_uuid,
            issue_now=issue_now,
            requires_acknowledgement=True,
        )
        directive = service.create_directive(payload, issued_by_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/directives?message=Directive+{directive.title}+issued", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/directives?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/directives/{directive_id}/acknowledge", response_class=HTMLResponse)
async def dev_acknowledge_directive(
    directive_id: UUID,
    request: Request,
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Acknowledges directive from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = DirectiveService(db)
        service.acknowledge_directive(directive_id, user_id=actor.id, data=DirectiveAcknowledgeRequest(notes=notes))
        db.commit()
        return RedirectResponse(url="/dev/directives?message=Directive+acknowledged+successfully", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/directives?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/notifications", response_class=HTMLResponse)
async def dev_notifications_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Personal notifications verification page."""
    current_user = get_current_dev_user(request, db)
    notifs = []
    total = 0
    unread = 0
    if current_user:
        service = NotificationService(db)
        notifs, total, unread = service.list_user_notifications(user_id=current_user.id, limit=100)

    return templates.TemplateResponse(
        request=request,
        name="dev_notifications.html",
        context={
            "title": "Notifications & Alerts",
            "current_user": current_user,
            "notifications": notifs,
            "total": total,
            "unread_count": unread,
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/notifications/read-all", response_class=HTMLResponse)
async def dev_mark_all_notifications_read(
    request: Request,
    db: Session = Depends(get_db),
):
    """Marks all user notifications as read."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = NotificationService(db)
        cnt = service.mark_all_as_read(user_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/notifications?message={cnt}+notifications+marked+as+read", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/notifications?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/communications", response_class=HTMLResponse)
async def dev_communications_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Communication Tracker verification page."""
    current_user = get_current_dev_user(request, db)
    service = CommunicationLogService(db)
    org_service = OrganizationService(db)

    logs, total = service.list_logs(limit=100)
    verticals = org_service.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_communications.html",
        context={
            "title": "Official Communication Tracker",
            "current_user": current_user,
            "logs": logs,
            "total": total,
            "verticals": verticals,
            "comm_types": list(CommunicationType),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/communications/create", response_class=HTMLResponse)
async def dev_create_communication_log(
    request: Request,
    subject: str = Form(...),
    communication_type: CommunicationType = Form(CommunicationType.OFFICIAL_MESSAGE),
    sender_info: str = Form(...),
    recipient_info: str = Form(...),
    vertical_id: Optional[str] = Form(None),
    reference_link: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates communication log from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = CommunicationLogService(db)
        vert_uuid = UUID(vertical_id) if vertical_id else None

        payload = CommunicationLogCreate(
            subject=subject,
            communication_type=communication_type,
            sender_info=sender_info,
            recipient_info=recipient_info,
            vertical_id=vert_uuid,
            reference_link=reference_link,
            remarks=remarks,
        )
        log = service.create_log(payload, created_by_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/communications?message=Communication+{log.subject}+recorded", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/communications?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/transfers", response_class=HTMLResponse)
async def dev_transfers_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Ownership Transfers verification page."""
    current_user = get_current_dev_user(request, db)
    service = OwnershipTransferService(db)
    user_service = UserService(db)
    task_service = TaskService(db)
    event_service = EventService(db)

    transfers, total = service.list_transfers(limit=100)
    users = user_service.list_users(limit=100)
    tasks, _ = task_service.list_tasks(limit=50)
    events, _ = event_service.list_events(limit=50)

    return templates.TemplateResponse(
        request=request,
        name="dev_transfers.html",
        context={
            "title": "Resource Ownership Transfers",
            "current_user": current_user,
            "transfers": transfers,
            "total": total,
            "users": users,
            "tasks": tasks,
            "events": events,
            "resource_types": list(TransferResourceType),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/transfers/create", response_class=HTMLResponse)
async def dev_create_transfer(
    request: Request,
    resource_type: TransferResourceType = Form(...),
    resource_id: UUID = Form(...),
    requested_owner_id: UUID = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db),
):
    """Initiates ownership transfer from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = OwnershipTransferService(db)
        payload = OwnershipTransferCreate(
            resource_type=resource_type,
            resource_id=resource_id,
            requested_owner_id=requested_owner_id,
            reason=reason,
        )
        transfer = service.request_transfer(payload, requested_by_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/transfers?message=Transfer+requested+for+{transfer.resource_type.value}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/transfers?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/transfers/{transfer_id}/review", response_class=HTMLResponse)
async def dev_review_transfer(
    transfer_id: UUID,
    request: Request,
    status_val: TransferStatus = Form(..., alias="status"),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Reviews and executes ownership transfer."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        service = OwnershipTransferService(db)
        payload = OwnershipTransferReviewRequest(status=status_val, remarks=remarks)
        transfer = service.review_transfer(transfer_id, reviewer_id=actor.id, data=payload)
        db.commit()
        return RedirectResponse(url=f"/dev/transfers?message=Transfer+{transfer.status.value}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/transfers?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/audit", response_class=HTMLResponse)
async def dev_audit_page(
    request: Request,
    action: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Immutable Audit Center verification page."""
    current_user = get_current_dev_user(request, db)
    audit_service = AuditService(db)

    actor_uuid = UUID(actor_id) if actor_id else None
    logs = audit_service.list_logs(limit=100, action=action, actor_id=actor_uuid, resource_type=resource_type, outcome=outcome)
    total = audit_service.count()

    return templates.TemplateResponse(
        request=request,
        name="dev_audit.html",
        context={
            "title": "Immutable Audit Center",
            "current_user": current_user,
            "audit_logs": logs,
            "total": total,
            "filter_action": action,
            "filter_resource": resource_type,
            "filter_outcome": outcome,
        },
    )


@dev_router.get("/config", response_class=HTMLResponse)
async def dev_config_page(
    request: Request,
    error: Optional[str] = None,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """System Configuration verification page."""
    current_user = get_current_dev_user(request, db)
    config_service = SystemConfigService(db)
    configs = config_service.list_configs()

    return templates.TemplateResponse(
        request=request,
        name="dev_config.html",
        context={
            "title": "System Configuration Repository",
            "current_user": current_user,
            "configs": configs,
            "value_types": list(ConfigValueType),
            "error": error,
            "message": message,
        },
    )


@dev_router.post("/config/create", response_class=HTMLResponse)
async def dev_create_config(
    request: Request,
    key: str = Form(...),
    value: str = Form(...),
    value_type: ConfigValueType = Form(ConfigValueType.STRING),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Creates system config from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        config_service = SystemConfigService(db)
        payload = SystemConfigCreate(key=key, value=value, value_type=value_type, description=description)
        cfg = config_service.create_config(payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/config?message=Config+{cfg.key}+created", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/config?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.post("/config/{key}/update", response_class=HTMLResponse)
async def dev_update_config(
    key: str,
    request: Request,
    value: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Updates system config from dev UI."""
    try:
        actor = get_current_dev_user(request, db)
        if not actor:
            return RedirectResponse(url="/dev/auth?error=Login+required", status_code=status.HTTP_303_SEE_OTHER)

        config_service = SystemConfigService(db)
        payload = SystemConfigUpdate(value=value, description=description)
        cfg = config_service.update_config(key, payload, actor_id=actor.id)
        db.commit()
        return RedirectResponse(url=f"/dev/config?message=Config+{cfg.key}+updated", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        return RedirectResponse(url=f"/dev/config?error={str(exc)}", status_code=status.HTTP_303_SEE_OTHER)


@dev_router.get("/health", response_class=HTMLResponse)
async def dev_health_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """System Health verification page."""
    current_user = get_current_dev_user(request, db)
    app_health = get_app_health()
    db_health = get_database_health()

    return templates.TemplateResponse(
        request=request,
        name="dev_health.html",
        context={
            "title": "System Health & Infrastructure Diagnostics",
            "current_user": current_user,
            "app_health": app_health,
            "db_health": db_health,
            "settings": settings,
        },
    )


@dev_router.get("/analytics", response_class=HTMLResponse)
async def dev_analytics_page(
    request: Request,
    vertical_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Operational Analytics verification page."""
    current_user = get_current_dev_user(request, db)
    analytics_service = AnalyticsService(db)
    org_service = OrganizationService(db)

    vert_uuid = UUID(vertical_id) if vertical_id else None
    op_analytics = analytics_service.get_operational_analytics(vertical_id=vert_uuid)
    admin_analytics = analytics_service.get_administrative_analytics()
    my_summary = analytics_service.get_my_summary(user=current_user) if current_user else None
    verticals = org_service.list_verticals()

    return templates.TemplateResponse(
        request=request,
        name="dev_analytics.html",
        context={
            "title": "Operational Intelligence & Analytics",
            "current_user": current_user,
            "operational": op_analytics,
            "admin_analytics": admin_analytics,
            "my_summary": my_summary,
            "verticals": verticals,
            "selected_vertical_id": vertical_id,
        },
    )


@dev_router.get("/admin-reports", response_class=HTMLResponse)
async def dev_admin_reports_page(
    request: Request,
    report_type: str = Query("tasks"),
    db: Session = Depends(get_db),
):
    """Administrative Reporting verification page."""
    current_user = get_current_dev_user(request, db)
    rep_service = AdminReportingService(db)

    report_data = None
    if report_type == "tasks":
        report_data = rep_service.get_task_completion_report()
    elif report_type == "events":
        report_data = rep_service.get_event_readiness_report()
    elif report_type == "issues":
        report_data = rep_service.get_issue_escalation_report()
    elif report_type == "meetings":
        report_data = rep_service.get_meeting_attendance_report()

    return templates.TemplateResponse(
        request=request,
        name="dev_admin_reports.html",
        context={
            "title": "Administrative Operational Reports",
            "current_user": current_user,
            "report_type": report_type,
            "report_data": report_data,
        },
    )
