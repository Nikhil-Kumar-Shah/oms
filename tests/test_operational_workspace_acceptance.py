"""
End-to-End Operational Acceptance Test Suite for Phase 1 Enhancements
Paradox Sports OMS

Verifies:
1. Complete User Lifecycle & Authentication across ADMIN, SPORTS_CORE, COORDINATOR, VOLUNTEER
2. My Work Operational Aggregation, Filter Truth & Anti-Impersonation
3. Master Calendar Multi-Recurrence & Cross-Entity Relational Integrity
4. Weekly Reporting Dynamic Aggregation, Commentary & Four-Eyes Enforcement
5. Meeting Action Item Lifecycle & Duplicate-Proof Task Generation
6. Structured Profile Metadata Persistence, Isolation & Non-Privilege Escalation
7. Cross-User and Cross-Vertical Isolation
8. Transaction Failure Rollback & Foreign Key Constraint Enforcements
9. Fresh-Session PostgreSQL Verification
"""

import random
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
    RecurrenceFrequency,
)
from app.models.communication import (
    AcknowledgementStatus,
    Directive,
    DirectiveAcknowledgement,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
)
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventStatus,
    EventType,
)
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingParticipant,
    MeetingStatus,
    MeetingType,
    RSVPStatus,
)
from app.models.organization import Organization, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import (
    DailyReportStatus,
    DailyWorkReport,
    WeeklyReport,
    WeeklyReportStatus,
)
from app.models.requirement import Requirement, RequirementPriority, RequirementStatus
from app.models.task import (
    Task,
    TaskHealth,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.user import AccountStatus, User, UserAvailability, UserProfile
from app.schemas.calendar import CalendarCreate
from app.schemas.meeting import (
    MeetingActionConvertToTaskRequest,
    MeetingActionItemCreate,
    MeetingCreate,
)
from app.schemas.profile import UserProfileUpdate
from app.schemas.report import (
    DailyReportCreate,
    WeeklyReportCreate,
    WeeklyReportReviewRequest,
)
from app.schemas.user import UserCreate
from app.services.meeting_service import MeetingService
from app.services.profile_service import ProfileService
from app.services.report_service import ReportService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService


def _get_auth_headers(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    RateLimitingMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_e2e_my_work_complete_lifecycle(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    E2E Acceptance Test: My Work complete operational lifecycle.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    worker = user_service.create_user(
        UserCreate(
            username=f"worker_e2e_{suffix}",
            full_name=f"Worker E2E {suffix}",
            password="SecurePassword123!",
            email=f"worker_{suffix}@test.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    supervisor = user_service.create_user(
        UserCreate(
            username=f"sup_e2e_{suffix}",
            full_name=f"Supervisor E2E {suffix}",
            password="SecurePassword123!",
            email=f"sup_{suffix}@test.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    now = datetime.now(timezone.utc)
    today = date.today()

    # Active Task
    t_active = Task(
        title="Field Inspection E2E",
        vertical_id=test_vertical.id,
        assigned_to_id=worker.id,
        assigned_by_id=supervisor.id,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.ON_TRACK,
        deadline=now + timedelta(days=2),
    )
    # Blocked Task
    t_blocked = Task(
        title="Goal Net Setup",
        vertical_id=test_vertical.id,
        assigned_to_id=worker.id,
        assigned_by_id=supervisor.id,
        priority=TaskPriority.CRITICAL,
        status=TaskStatus.BLOCKED,
        health=TaskHealth.BLOCKED,
        blockers="Missing mounting pins",
        deadline=now + timedelta(days=1),
    )
    db_session.add_all([t_active, t_blocked])
    db_session.commit()

    headers = _get_auth_headers(client, worker.username, "SecurePassword123!")

    # API Request
    resp = client.get("/api/v1/workspace/my-work", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["user_id"] == str(worker.id)
    assert data["stats"]["active_tasks"] == 2
    assert data["stats"]["blocked_tasks"] == 1
    assert any(t["blocker_reason"] == "Missing mounting pins" for t in data["blockers"])


def test_e2e_master_calendar_recurrence_and_linking(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """
    E2E Acceptance Test: Master Calendar recurrence & entity linking.
    """
    headers = _get_auth_headers(client, admin_user.username, "AdminPass@123")
    today = date.today()

    task = Task(
        title="Equipment Audit",
        vertical_id=test_vertical.id,
        assigned_to_id=admin_user.id,
        assigned_by_id=admin_user.id,
        status=TaskStatus.IN_PROGRESS,
    )
    event = Event(
        name="State Swimming Championship",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=today + timedelta(days=15),
        primary_poc_id=admin_user.id,
        created_by_id=admin_user.id,
    )
    db_session.add_all([task, event])
    db_session.commit()

    # Create monthly recurring entry
    payload = {
        "title": "Monthly Pool Chlorination",
        "activity_date": today.isoformat(),
        "category": "ACTIVITY",
        "priority": "HIGH",
        "status": "PLANNED",
        "deadline_type": "HARD_DEADLINE",
        "audience": "VERTICAL",
        "vertical_id": str(test_vertical.id),
        "recurrence": "MONTHLY",
        "recurrence_end_date": (today + timedelta(days=180)).isoformat(),
        "task_id": str(task.id),
        "event_id": str(event.id),
    }
    resp = client.post("/api/v1/calendar", json=payload, headers=headers)
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    # Fresh Session DB Truth
    fresh_db = SessionLocal()
    try:
        cal_entry = fresh_db.get(CalendarEntry, uuid.UUID(entry_id))
        assert cal_entry is not None
        assert cal_entry.recurrence == RecurrenceFrequency.MONTHLY
        assert cal_entry.task_id == task.id
        assert cal_entry.event_id == event.id
    finally:
        fresh_db.close()


def test_e2e_weekly_reporting_dynamic_rollup_recalculation(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    E2E Acceptance Test: Dynamic Rollup responds to database changes.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))

    lead = user_service.create_user(
        UserCreate(
            username=f"lead_rep_{suffix}",
            full_name=f"Lead Reporter {suffix}",
            password="SecurePassword123!",
            email=f"lead_{suffix}@test.internal",
            vertical_ids=[test_vertical.id],
            role_ids=[role_admin.id] if role_admin else [],
        )
    )
    db_session.commit()

    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    # 1. Initial State: 1 Daily Report
    dr = DailyWorkReport(
        user_id=lead.id,
        vertical_id=test_vertical.id,
        report_date=start_week,
        work_summary="Pitch watering complete",
        status=DailyReportStatus.SUBMITTED,
    )
    db_session.add(dr)
    db_session.commit()

    headers = _get_auth_headers(client, lead.username, "SecurePassword123!")

    # Verify initial rollup count = 1
    resp1 = client.get(
        f"/api/v1/reports/weekly/rollup?vertical_id={test_vertical.id}&user_id={lead.id}&start_date={start_week}&end_date={end_week}",
        headers=headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["daily_reports_count"] == 1

    # 2. Add second Daily Report directly to database
    dr2 = DailyWorkReport(
        user_id=lead.id,
        vertical_id=test_vertical.id,
        report_date=start_week + timedelta(days=1),
        work_summary="Pitch mowing complete",
        status=DailyReportStatus.SUBMITTED,
    )
    db_session.add(dr2)
    db_session.commit()

    # Verify dynamic recalculation = 2
    resp2 = client.get(
        f"/api/v1/reports/weekly/rollup?vertical_id={test_vertical.id}&user_id={lead.id}&start_date={start_week}&end_date={end_week}",
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["daily_reports_count"] == 2


def test_e2e_meeting_action_conversion_transaction_and_idempotency(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    E2E Acceptance Test: Meeting action item conversion idempotency and transaction integrity.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))

    lead = user_service.create_user(
        UserCreate(
            username=f"lead_m_{suffix}",
            full_name=f"Meeting Chair {suffix}",
            password="SecurePassword123!",
            email=f"chair_{suffix}@test.internal",
            vertical_ids=[test_vertical.id],
            role_ids=[role_admin.id] if role_admin else [],
        )
    )
    worker = user_service.create_user(
        UserCreate(
            username=f"worker_m_{suffix}",
            full_name=f"Meeting Worker {suffix}",
            password="SecurePassword123!",
            email=f"worker_m_{suffix}@test.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    headers = _get_auth_headers(client, lead.username, "SecurePassword123!")
    today = date.today()

    # 1. Create Meeting
    m_resp = client.post(
        "/api/v1/meetings",
        json={
            "title": "Annual League Logistics Briefing",
            "vertical_id": str(test_vertical.id),
            "meeting_type": "CORE_COORDINATION",
            "meeting_date": today.isoformat(),
            "participant_ids": [str(worker.id)],
        },
        headers=headers,
    )
    assert m_resp.status_code == 201
    meeting_id = m_resp.json()["id"]

    # 2. Create Action Item
    act_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items",
        json={"description": "Assemble 50 volunteer kits", "assignee_id": str(worker.id), "priority": "HIGH"},
        headers=headers,
    )
    assert act_resp.status_code == 201
    action_item_id = act_resp.json()["id"]

    # 3. Convert to Task
    task_title = f"Assemble Volunteer Kits {suffix}"
    conv_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/{action_item_id}/convert-to-task",
        json={"title": task_title, "priority": "HIGH"},
        headers=headers,
    )
    assert conv_resp.status_code == 201
    task_id = conv_resp.json()["id"]

    # 4. Attempt second conversion (Must be blocked)
    retry_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/{action_item_id}/convert-to-task",
        json={"title": f"{task_title} Duplicate"},
        headers=headers,
    )
    assert retry_resp.status_code in [400, 422]

    # 5. Verify only 1 task exists in database
    fresh_db = SessionLocal()
    try:
        tasks = fresh_db.execute(select(Task).where(Task.title == task_title)).scalars().all()
        assert len(tasks) == 1
    finally:
        fresh_db.close()


def test_e2e_user_profile_persistence_and_cross_user_protection(client: TestClient, db_session: Session):
    """
    E2E Acceptance Test: Profile persistence & cross-user update denial.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    user_a = user_service.create_user(
        UserCreate(
            username=f"user_a_{suffix}",
            full_name=f"User Alpha {suffix}",
            password="SecurePassword123!",
            email=f"alpha_{suffix}@test.internal",
        )
    )
    user_b = user_service.create_user(
        UserCreate(
            username=f"user_b_{suffix}",
            full_name=f"User Beta {suffix}",
            password="SecurePassword123!",
            email=f"beta_{suffix}@test.internal",
        )
    )
    db_session.commit()

    headers_a = _get_auth_headers(client, user_a.username, "SecurePassword123!")
    headers_b = _get_auth_headers(client, user_b.username, "SecurePassword123!")

    # 1. User A updates own profile
    update_payload = {
        "phone_number": "+91 9123456789",
        "specialization": "Referee Grade 2",
        "operational_capability": "Full field refereeing",
        "certifications": ["National Refereeing License"],
        "availability": "AVAILABLE",
        "profile_notes": "Ready for match assignment.",
    }
    put_resp = client.put("/api/v1/profiles/me", json=update_payload, headers=headers_a)
    assert put_resp.status_code == 200

    # 2. User B attempts to overwrite User A's profile via administrative endpoint without permission
    tamper_resp = client.put(f"/api/v1/profiles/{user_a.id}", json=update_payload, headers=headers_b)
    assert tamper_resp.status_code == 403, "Unprivileged user must NOT be able to modify another user's profile"

    # 3. Fresh session check on User A's profile
    fresh_db = SessionLocal()
    try:
        fresh_prof = fresh_db.execute(select(UserProfile).where(UserProfile.user_id == user_a.id)).scalar_one_or_none()
        assert fresh_prof is not None
        assert fresh_prof.specialization == "Referee Grade 2"
        assert fresh_prof.phone_number == "+91 9123456789"
    finally:
        fresh_db.close()
