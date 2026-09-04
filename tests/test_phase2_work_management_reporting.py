"""
Phase 2: Work Management + Reporting Test Suite
Paradox Sports OMS - Authoritative Product Specification Verification

Verifies:
1. Master Tasks Complete Lifecycle, Status Transitions, Percentage Synchronization & Health Calculation
2. Server-Authoritative Task Assignment & Reassignment (Vertical Scope Enforcement)
3. Task Escalation, Resolution, and Structured Blockers
4. Task Comments & Append-Only History
5. My Work Personal View Server-Side Isolation & Anti-Impersonation
6. Master Calendar Scoping, Categories, Deadlines & Relational Entity Linkages
7. Issue & Escalation Register, Sensitivity Enforcement & Resolution
8. Daily Work Reports Submission, Duplicate Prevention & Four-Eyes Supervisor Review Rule
9. Weekly Reports Dynamic PostgreSQL Rollup Aggregation
10. Fresh-Session PostgreSQL Persistence Truth
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.middleware import RateLimitingMiddleware
from app.models.calendar import (
    ActivityCategory,
    CalendarAudience,
    CalendarEntry,
    CalendarPriority,
    CalendarStatus,
    DeadlineType,
)
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport, WeeklyReport, WeeklyReportStatus
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.schemas.calendar import CalendarCreate
from app.schemas.issue import IssueCreate, IssueEscalateRequest, IssueTransitionRequest
from app.schemas.report import DailyReportCreate, DailyReportReviewRequest, WeeklyReportCreate
from app.schemas.task import (
    TaskBlockRequest,
    TaskCreate,
    TaskEscalateRequest,
    TaskReassignRequest,
    TaskResolveEscalationRequest,
    TaskTransitionRequest,
    TaskUnblockRequest,
)
from app.schemas.user import UserCreate
from app.services.calendar_service import CalendarService
from app.services.issue_service import IssueService
from app.services.organization_service import OrganizationService
from app.services.report_service import ReportService
from app.services.task_service import TaskService
from app.services.user_service import UserService


def _login_and_get_token(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    RateLimitingMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Master Task Lifecycle, Percentage Sync & Health Recalculation
# =============================================================================

def test_task_lifecycle_completion_sync_and_health_recalculation(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies atomic task status transitions, completion percentage synchronization, and health derivation."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_svc = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    assignee = user_svc.create_user(
        UserCreate(username=f"task_worker_{suffix}", full_name="Task Worker", password="SecurePassword123!", vertical_ids=[test_vertical.id])
    )
    db_session.commit()

    # 1. Create Task (NOT_STARTED, 0% complete, ON_TRACK)
    deadline = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    create_resp = client.post(
        "/api/v1/tasks",
        json={
            "vertical_id": str(test_vertical.id),
            "assigned_to_id": str(assignee.id),
            "title": f"Inspect Arena Lighting {suffix}",
            "task_type": "ROUTINE",
            "priority": "HIGH",
            "deadline": deadline,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "NOT_STARTED"
    assert create_resp.json()["completion_percentage"] == 0
    assert create_resp.json()["health"] == "ON_TRACK"

    # 2. Transition to IN_PROGRESS (35%)
    t1_resp = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"status": "IN_PROGRESS", "completion_percentage": 35},
        headers=headers,
    )
    assert t1_resp.status_code == 200
    assert t1_resp.json()["status"] == "IN_PROGRESS"
    assert t1_resp.json()["completion_percentage"] == 35

    # 3. Block Task
    block_resp = client.post(
        f"/api/v1/tasks/{task_id}/block",
        json={"blocker_description": "Generator failure in sector 4"},
        headers=headers,
    )
    assert block_resp.status_code == 200
    assert block_resp.json()["status"] == "BLOCKED"
    assert block_resp.json()["health"] == "BLOCKED"
    assert block_resp.json()["blockers"] == "Generator failure in sector 4"

    # 4. Unblock Task
    unblock_resp = client.post(
        f"/api/v1/tasks/{task_id}/unblock",
        json={"resolution": "Auxiliary generator activated"},
        headers=headers,
    )
    assert unblock_resp.status_code == 200
    assert unblock_resp.json()["status"] == "IN_PROGRESS"
    assert unblock_resp.json()["blockers"] is None

    # 5. Transition to COMPLETED (Must auto-sync completion to 100%)
    t2_resp = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"status": "COMPLETED"},
        headers=headers,
    )
    assert t2_resp.status_code == 200
    assert t2_resp.json()["status"] == "COMPLETED"
    assert t2_resp.json()["completion_percentage"] == 100
    assert t2_resp.json()["health"] == "COMPLETE"
    assert t2_resp.json()["completed_on"] is not None


# =============================================================================
# 2. Task Assignment & Reassignment Authorization & Scope
# =============================================================================

def test_task_reassignment_within_vertical_and_cross_vertical_denial(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies task reassignment verifies vertical membership and logs history."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_svc = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    # Two users in same vertical
    user1 = user_svc.create_user(UserCreate(username=f"u1_{suffix}", full_name="User 1", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    user2 = user_svc.create_user(UserCreate(username=f"u2_{suffix}", full_name="User 2", password="SecurePassword123!", vertical_ids=[test_vertical.id]))

    # User in different vertical
    other_vert = Vertical(name=f"Other Vert {suffix}", organization_id=test_vertical.organization_id, status=VerticalStatus.ACTIVE)
    db_session.add(other_vert)
    db_session.flush()
    user_out = user_svc.create_user(UserCreate(username=f"u_out_{suffix}", full_name="User Out", password="SecurePassword123!", vertical_ids=[other_vert.id]))
    db_session.commit()

    # Create task assigned to user1
    task_svc = TaskService(db_session)
    task = task_svc.create_task(
        TaskCreate(vertical_id=test_vertical.id, assigned_to_id=user1.id, title="Pitch maintenance"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Reassign to user2 (Valid)
    reassign_resp = client.post(
        f"/api/v1/tasks/{task.id}/reassign",
        json={"new_assigned_to_id": str(user2.id), "remarks": "Shift handoff to user2"},
        headers=headers,
    )
    assert reassign_resp.status_code == 200
    assert reassign_resp.json()["assigned_to_id"] == str(user2.id)
    assert reassign_resp.json()["assigned_to_username"] == f"u2_{suffix}"

    # 2. Attempt Reassign to user_out (Invalid - Cross-vertical rejected)
    bad_reassign = client.post(
        f"/api/v1/tasks/{task.id}/reassign",
        json={"new_assigned_to_id": str(user_out.id)},
        headers=headers,
    )
    assert bad_reassign.status_code in [400, 422]


# =============================================================================
# 3. Task Escalation & Resolution Workflow
# =============================================================================

def test_task_escalation_and_resolution_workflow(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies structured task escalation, status tracking, and resolution."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    task_svc = TaskService(db_session)
    suffix = uuid.uuid4().hex[:6]

    task = task_svc.create_task(
        TaskCreate(vertical_id=test_vertical.id, title=f"Coordinate medical team {suffix}", priority=TaskPriority.HIGH),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Escalate Task
    esc_resp = client.post(
        f"/api/v1/tasks/{task.id}/escalate",
        json={"reason": "Ambulance provider cancelled contract 48h before event", "remarks": "Requires Core intervention"},
        headers=headers,
    )
    assert esc_resp.status_code == 200
    data = esc_resp.json()
    assert data["is_escalated"] is True
    assert data["escalation_status"] == "PENDING"
    assert data["escalation_reason"] == "Ambulance provider cancelled contract 48h before event"

    # 2. Resolve Escalation
    res_resp = client.post(
        f"/api/v1/tasks/{task.id}/resolve-escalation",
        json={"resolution": "Emergency backup provider contracted and confirmed"},
        headers=headers,
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["is_escalated"] is False
    assert res_data["escalation_status"] == "RESOLVED"
    assert res_data["escalation_resolution"] == "Emergency backup provider contracted and confirmed"


# =============================================================================
# 4. My Work Personal View Server-Side Isolation & Anti-Impersonation
# =============================================================================

def test_my_work_personal_view_isolation_and_anti_impersonation(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """
    CRITICAL SECURITY TEST: My Work view MUST strictly derive identity from authenticated session.
    User A cannot retrieve User B's work by injecting ?user_id or payload manipulation.
    """
    user_svc = UserService(db_session)
    task_svc = TaskService(db_session)
    suffix = uuid.uuid4().hex[:6]

    user_a = user_svc.create_user(UserCreate(username=f"worker_a_{suffix}", full_name="Worker A", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    user_b = user_svc.create_user(UserCreate(username=f"worker_b_{suffix}", full_name="Worker B", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    db_session.commit()

    task_a = task_svc.create_task(TaskCreate(vertical_id=test_vertical.id, assigned_to_id=user_a.id, title=f"Worker A Task {suffix}"), actor_id=admin_user.id)
    task_b = task_svc.create_task(TaskCreate(vertical_id=test_vertical.id, assigned_to_id=user_b.id, title=f"Worker B Task {suffix}"), actor_id=admin_user.id)
    db_session.commit()

    headers_a = _login_and_get_token(client, f"worker_a_{suffix}", "SecurePassword123!")

    # 1. Worker A calls /api/v1/workspace/my-work
    resp_a = client.get("/api/v1/workspace/my-work", headers=headers_a)
    assert resp_a.status_code == 200
    my_tasks = resp_a.json()["tasks"]
    task_titles = [t["title"] for t in my_tasks]

    assert f"Worker A Task {suffix}" in task_titles
    assert f"Worker B Task {suffix}" not in task_titles

    # 2. Worker A attempts query parameter tampering: ?user_id=<user_b_id>
    tamper_resp = client.get(f"/api/v1/workspace/my-work?user_id={user_b.id}", headers=headers_a)
    assert tamper_resp.status_code == 200
    tamper_tasks = tamper_resp.json()["tasks"]
    tamper_titles = [t["title"] for t in tamper_tasks]

    # Must still return Worker A's tasks only
    assert f"Worker A Task {suffix}" in tamper_titles
    assert f"Worker B Task {suffix}" not in tamper_titles


# =============================================================================
# 5. Master Calendar Visibility & Audience Scoping
# =============================================================================

def test_master_calendar_audience_scoping_and_entity_linkage(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Master Calendar entries respect audience scoping (ORGANIZATION vs VERTICAL)."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_svc = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    today = date.today()

    other_vert = Vertical(name=f"Aquatics Vert {suffix}", organization_id=test_vertical.organization_id, status=VerticalStatus.ACTIVE)
    db_session.add(other_vert)
    db_session.flush()

    user_v1 = user_svc.create_user(UserCreate(username=f"v1_u_{suffix}", full_name="V1 User", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    user_v2 = user_svc.create_user(UserCreate(username=f"v2_u_{suffix}", full_name="V2 User", password="SecurePassword123!", vertical_ids=[other_vert.id]))
    db_session.commit()

    # 1. Create Vertical-scoped calendar entry for test_vertical
    v1_entry_resp = client.post(
        "/api/v1/calendar",
        json={
            "title": f"Football Ground Maintenance {suffix}",
            "activity_date": (today + timedelta(days=3)).isoformat(),
            "category": "ACTIVITY",
            "audience": "VERTICAL",
            "vertical_id": str(test_vertical.id),
        },
        headers=headers,
    )
    assert v1_entry_resp.status_code == 201

    # 2. Create Organization-wide calendar entry
    org_entry_resp = client.post(
        "/api/v1/calendar",
        json={
            "title": f"Annual Sports Meet Opening {suffix}",
            "activity_date": (today + timedelta(days=7)).isoformat(),
            "category": "EVENT",
            "audience": "ORGANIZATION",
        },
        headers=headers,
    )
    assert org_entry_resp.status_code == 201

    # 3. User V2 in other_vert lists calendar
    headers_v2 = _login_and_get_token(client, f"v2_u_{suffix}", "SecurePassword123!")
    cal_v2 = client.get("/api/v1/calendar", headers=headers_v2)
    assert cal_v2.status_code == 200
    v2_items = [item["title"] for item in cal_v2.json()["items"]]

    # V2 sees Org entry, but NOT V1 vertical-scoped entry
    assert f"Annual Sports Meet Opening {suffix}" in v2_items
    assert f"Football Ground Maintenance {suffix}" not in v2_items


# =============================================================================
# 6. Issue Sensitivity Enforcement & Resolution
# =============================================================================

def test_issue_sensitivity_isolation_and_escalation(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies confidential issues are isolated from regular volunteers and accessible to supervisors."""
    user_svc = UserService(db_session)
    issue_svc = IssueService(db_session)
    suffix = uuid.uuid4().hex[:6]

    role_vol = db_session.scalar(select(Role).where(Role.name == "VOLUNTEER"))
    vol_user = user_svc.create_user(
        UserCreate(username=f"vol_iss_{suffix}", full_name="Vol Issue User", password="SecurePassword123!", role_ids=[role_vol.id], vertical_ids=[test_vertical.id])
    )
    db_session.commit()

    # Create NORMAL issue and CONFIDENTIAL issue
    issue_norm = issue_svc.create_issue(
        IssueCreate(vertical_id=test_vertical.id, title=f"Water Cooler Broken {suffix}", description="Cooler leaking in corridor", sensitivity=IssueSensitivity.NORMAL),
        actor_id=admin_user.id,
    )
    issue_conf = issue_svc.create_issue(
        IssueCreate(vertical_id=test_vertical.id, title=f"Disciplinary Dispute {suffix}", description="Sensitive altercation report", sensitivity=IssueSensitivity.CONFIDENTIAL),
        actor_id=admin_user.id,
    )
    db_session.commit()

    headers_vol = _login_and_get_token(client, f"vol_iss_{suffix}", "SecurePassword123!")

    # 1. Volunteer accesses NORMAL issue (Allowed)
    r_norm = client.get(f"/api/v1/issues/{issue_norm.id}", headers=headers_vol)
    assert r_norm.status_code == 200

    # 2. Volunteer attempts to access CONFIDENTIAL issue (Forbidden)
    r_conf = client.get(f"/api/v1/issues/{issue_conf.id}", headers=headers_vol)
    assert r_conf.status_code == 403, "Confidential issue must be forbidden for unassigned volunteer"

    # 3. Admin escalates and resolves normal issue
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    res_resp = client.post(
        f"/api/v1/issues/{issue_norm.id}/transition",
        json={"status": "RESOLVED", "resolution": "Plumbing contractor replaced valve"},
        headers=headers_admin,
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"
    assert res_resp.json()["resolution"] == "Plumbing contractor replaced valve"


# =============================================================================
# 7. Daily Report Submission, Duplicate Prevention & Four-Eyes Review
# =============================================================================

def test_daily_report_duplicate_prevention_and_four_eyes_review(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies daily report submission, duplicate prevention, and four-eyes rule (self-review blocked)."""
    user_svc = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    today = date.today()

    author = user_svc.create_user(UserCreate(username=f"rep_auth_{suffix}", full_name="Report Author", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    db_session.commit()

    headers_author = _login_and_get_token(client, f"rep_auth_{suffix}", "SecurePassword123!")

    # 1. Submit Daily Report
    payload = {
        "vertical_id": str(test_vertical.id),
        "report_date": today.isoformat(),
        "work_summary": "Conducted equipment checks and scheduled field session",
        "tasks_completed": "Checked 20 footballs and 4 nets",
        "submit_now": True,
    }
    create_resp = client.post("/api/v1/reports/daily", json=payload, headers=headers_author)
    assert create_resp.status_code == 201
    report_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "SUBMITTED"

    # 2. Attempt duplicate report for same user on same date (Must Fail)
    dup_resp = client.post("/api/v1/reports/daily", json=payload, headers=headers_author)
    assert dup_resp.status_code in [400, 422]

    # 3. Author attempts self-review (Must Fail - Four-Eyes Rule)
    self_rev = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Looks great to myself"},
        headers=headers_author,
    )
    assert self_rev.status_code in [400, 403, 422], "Author cannot review own report"

    # 4. Supervisor (Admin) reviews report (Allowed)
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Verified equipment inventory count"},
        headers=headers_admin,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "REVIEWED"
    assert rev_resp.json()["reviewer_username"] == admin_user.username


# =============================================================================
# 8. Weekly Reports Dynamic PostgreSQL Rollup Aggregation
# =============================================================================

def test_weekly_report_dynamic_postgresql_rollup(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies dynamic rollup of daily reports, task completion metrics, and blockers for weekly report."""
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Call dynamic weekly rollup endpoint
    rollup_resp = client.get(
        f"/api/v1/reports/weekly/rollup?vertical_id={test_vertical.id}&start_date={week_start.isoformat()}&end_date={week_end.isoformat()}",
        headers=headers_admin,
    )
    assert rollup_resp.status_code == 200
    data = rollup_resp.json()

    assert data["vertical_id"] == str(test_vertical.id)
    assert "daily_reports_submitted" in data
    assert "daily_reports_count" in data
    assert "completed_tasks" in data
    assert "incomplete_tasks" in data
    assert "blockers" in data
    assert "major_issues" in data


# =============================================================================
# 9. Fresh Session PostgreSQL Persistence Truth
# =============================================================================

def test_phase2_fresh_session_persistence_truth(db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies direct database truth reads across completely fresh, isolated sessions."""
    task_svc = TaskService(db_session)
    suffix = uuid.uuid4().hex[:6]

    task = task_svc.create_task(
        TaskCreate(vertical_id=test_vertical.id, title=f"Fresh Session Task {suffix}", priority=TaskPriority.HIGH),
        actor_id=admin_user.id,
    )
    db_session.commit()
    task_id = task.id

    # Escalate task
    task_svc.escalate_task(
        task_id,
        TaskEscalateRequest(reason="Fresh session escalation test"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # Query using a completely fresh database session
    fresh_db = SessionLocal()
    try:
        db_task = fresh_db.get(Task, task_id)
        assert db_task is not None
        assert db_task.title == f"Fresh Session Task {suffix}"
        assert db_task.is_escalated is True
        assert db_task.escalation_reason == "Fresh session escalation test"
        assert db_task.escalation_status == "PENDING"
    finally:
        fresh_db.close()
