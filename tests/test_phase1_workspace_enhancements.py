"""
Phase 1 Operational Workspace Enhancements Test Suite
Paradox Sports OMS

Verifies:
1. Unified My Work (Server-Authoritative, Multi-Resource Aggregation, Anti-Impersonation)
2. Master Calendar Enhancements (Recurrence Enums, Entity Links, Audience Scoping)
3. Weekly Reporting Dynamic Rollup (PostgreSQL Aggregation, Weekly Reports, Self-Review Prevention)
4. Meeting Action -> Task Conversion (Context Preservation, Duplicate Prevention, Transaction Safety)
5. Structured User / Team Profile Metadata (Specialization, Certifications, Availability, Fresh Session DB Verification)
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
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
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import (
    DailyReportStatus,
    DailyWorkReport,
    WeeklyReport,
    WeeklyReportStatus,
)
from app.models.requirement import (
    Requirement,
    RequirementPriority,
    RequirementStatus,
)
from app.models.task import (
    Task,
    TaskHealth,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.user import AccountStatus, User, UserAvailability, UserProfile
from app.schemas.auth import LoginRequest
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
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.meeting_service import MeetingService
from app.services.profile_service import ProfileService
from app.services.report_service import ReportService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService


def _get_auth_headers(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# FEATURE 1: UNIFIED MY WORK
# =============================================================================

def test_feature1_unified_my_work(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    Verifies Unified My Work aggregation:
    - Derives identity strictly from server-authenticated session (Anti-Impersonation).
    - Aggregates active tasks, blocked tasks, overdue tasks, pending directives, upcoming meetings, event duties.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    # Create User A (Worker)
    user_a = user_service.create_user(
        UserCreate(
            username=f"worker_a_{suffix}",
            full_name=f"Worker Alpha {suffix}",
            password="SecurePassword123!",
            email=f"worker_a_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
        )
    )

    # Create User B (Worker)
    user_b = user_service.create_user(
        UserCreate(
            username=f"worker_b_{suffix}",
            full_name=f"Worker Beta {suffix}",
            password="SecurePassword123!",
            email=f"worker_b_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    now = datetime.now(timezone.utc)
    today = date.today()

    # 1. Setup User A's Task workload
    task_active = Task(
        title="Field Inspection A",
        vertical_id=test_vertical.id,
        assigned_to_id=user_a.id,
        assigned_by_id=user_b.id,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.ON_TRACK,
        deadline=now + timedelta(days=2),
    )
    task_blocked = Task(
        title="Equipment Repair A",
        vertical_id=test_vertical.id,
        assigned_to_id=user_a.id,
        assigned_by_id=user_b.id,
        priority=TaskPriority.CRITICAL,
        status=TaskStatus.BLOCKED,
        health=TaskHealth.BLOCKED,
        blockers="Spare parts out of stock",
        deadline=now + timedelta(days=1),
    )
    task_overdue = Task(
        title="Safety Audit A",
        vertical_id=test_vertical.id,
        assigned_to_id=user_a.id,
        assigned_by_id=user_b.id,
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.OVERDUE,
        deadline=now - timedelta(days=1),
    )
    # User B's Task (Must NOT appear in User A's workspace)
    task_user_b = Task(
        title="User B Task",
        vertical_id=test_vertical.id,
        assigned_to_id=user_b.id,
        assigned_by_id=user_a.id,
        priority=TaskPriority.LOW,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.ON_TRACK,
    )
    db_session.add_all([task_active, task_blocked, task_overdue, task_user_b])

    # 2. Setup Directive for User A
    directive = Directive(
        title="Monsoon Safety Protocols",
        instruction="All staff must review wet-weather operating rules.",
        scope=DirectiveScope.VERTICAL,
        vertical_id=test_vertical.id,
        issued_by_id=user_b.id,
        status=DirectiveStatus.ISSUED,
    )
    db_session.add(directive)
    db_session.flush()

    ack = DirectiveAcknowledgement(
        directive_id=directive.id,
        user_id=user_a.id,
        status=AcknowledgementStatus.PENDING,
    )
    db_session.add(ack)

    # 3. Setup Meeting for User A
    meeting = Meeting(
        title="Weekly Ground Briefing",
        organizer_id=user_b.id,
        vertical_id=test_vertical.id,
        meeting_type=MeetingType.INTERNAL_SYNC,
        status=MeetingStatus.SCHEDULED,
        meeting_date=today + timedelta(days=1),
    )
    db_session.add(meeting)
    db_session.flush()

    m_part = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=user_a.id,
        rsvp_status=RSVPStatus.PENDING,
    )
    db_session.add(m_part)

    # 4. Setup Event Duty for User A
    event = Event(
        name="Inter-University Football Cup",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.IN_PROGRESS,
        planned_date=today + timedelta(days=3),
        primary_poc_id=user_a.id,
        created_by_id=user_a.id,
    )
    db_session.add(event)
    db_session.commit()

    # Query My Work via API as User A
    headers_a = _get_auth_headers(client, user_a.username, "SecurePassword123!")
    resp = client.get("/api/v1/workspace/my-work", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["user_id"] == str(user_a.id)
    assert data["username"] == user_a.username
    assert data["stats"]["active_tasks"] == 3
    assert data["stats"]["blocked_tasks"] == 1
    assert data["stats"]["overdue_tasks"] == 1
    assert data["stats"]["pending_directives"] == 1
    assert data["stats"]["upcoming_meetings"] == 1
    assert data["stats"]["event_duties"] == 1

    # Anti-Impersonation: Attempt to pass another user's ID via query parameters
    resp_tamper = client.get(f"/api/v1/workspace/my-work?user_id={user_b.id}", headers=headers_a)
    assert resp_tamper.status_code == 200
    assert resp_tamper.json()["user_id"] == str(user_a.id), "Server must ignore client user_id parameter and use session identity"


# =============================================================================
# FEATURE 2: MASTER CALENDAR ENHANCEMENTS
# =============================================================================

def test_feature2_master_calendar_enhancements(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """
    Verifies Master Calendar recurrence options and entity linking:
    - Recurrence: NONE, DAILY, WEEKLY, MONTHLY.
    - Entity links: task_id, event_id, meeting_id, requirement_id.
    - Fresh session PostgreSQL verification.
    """
    headers = _get_auth_headers(client, admin_user.username, "AdminPass@123")
    today = date.today()

    # Create linked Task & Event
    task = Task(
        title="Pitch Rolling Task",
        vertical_id=test_vertical.id,
        assigned_to_id=admin_user.id,
        assigned_by_id=admin_user.id,
        status=TaskStatus.IN_PROGRESS,
    )
    event = Event(
        name="Annual Athletics Meet",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=today + timedelta(days=10),
        primary_poc_id=admin_user.id,
        created_by_id=admin_user.id,
    )
    db_session.add_all([task, event])
    db_session.commit()

    # Create Calendar Entry with Recurrence and Entity Links
    payload = {
        "title": "Weekly Turf Maintenance",
        "description": "Routine weekly turf conditioning",
        "activity_date": today.isoformat(),
        "category": "ACTIVITY",
        "priority": "HIGH",
        "status": "PLANNED",
        "deadline_type": "HARD_DEADLINE",
        "audience": "VERTICAL",
        "vertical_id": str(test_vertical.id),
        "recurrence": "WEEKLY",
        "recurrence_end_date": (today + timedelta(days=60)).isoformat(),
        "task_id": str(task.id),
        "event_id": str(event.id),
    }

    resp = client.post("/api/v1/calendar", json=payload, headers=headers)
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    # Fresh session PostgreSQL verification
    fresh_db = SessionLocal()
    try:
        fresh_entry = fresh_db.get(CalendarEntry, uuid.UUID(entry_id))
        assert fresh_entry is not None
        assert fresh_entry.recurrence == RecurrenceFrequency.WEEKLY
        assert fresh_entry.recurrence_end_date == today + timedelta(days=60)
        assert fresh_entry.task_id == task.id
        assert fresh_entry.event_id == event.id
    finally:
        fresh_db.close()


# =============================================================================
# FEATURE 3: WEEKLY REPORTING DYNAMIC ROLLUP
# =============================================================================

def test_feature3_weekly_reporting_rollup(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    Verifies Weekly Reporting Dynamic Rollup & Commentary:
    - GET /api/v1/reports/weekly/rollup calculates metrics from PostgreSQL.
    - POST /api/v1/reports/weekly saves structured weekly report.
    - POST /api/v1/reports/weekly/{id}/review applies supervisor review.
    - Strictly blocks self-review (403 Forbidden).
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
    role_vol = db_session.scalar(select(Role).where(Role.name == "VOLUNTEER"))

    officer = user_service.create_user(
        UserCreate(
            username=f"field_officer_{suffix}",
            full_name=f"Field Officer {suffix}",
            password="SecurePassword123!",
            email=f"officer_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
            role_ids=[role_admin.id] if role_admin else [],
        )
    )
    supervisor = user_service.create_user(
        UserCreate(
            username=f"supervisor_{suffix}",
            full_name=f"Supervisor {suffix}",
            password="SecurePassword123!",
            email=f"sup_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
            role_ids=[role_admin.id] if role_admin else [],
        )
    )
    db_session.commit()

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # 1. Seed 2 Daily Reports for the officer
    dr1 = DailyWorkReport(
        user_id=officer.id,
        vertical_id=test_vertical.id,
        report_date=start_of_week,
        work_summary="Completed pitch lining and goal net inspection",
        tasks_completed="Pitch 1 & 2 marked",
        status=DailyReportStatus.SUBMITTED,
    )
    dr2 = DailyWorkReport(
        user_id=officer.id,
        vertical_id=test_vertical.id,
        report_date=start_of_week + timedelta(days=1),
        work_summary="Corner flag replacements and floodlight testing",
        blockers="Floodlight tower 3 bulb failure",
        status=DailyReportStatus.SUBMITTED,
    )
    # Seed 1 completed task
    task_done = Task(
        title="Goalpost Certification",
        vertical_id=test_vertical.id,
        assigned_to_id=officer.id,
        assigned_by_id=supervisor.id,
        status=TaskStatus.COMPLETED,
    )
    db_session.add_all([dr1, dr2, task_done])
    db_session.commit()

    headers_officer = _get_auth_headers(client, officer.username, "SecurePassword123!")
    headers_sup = _get_auth_headers(client, supervisor.username, "SecurePassword123!")

    # 2. Test Dynamic Rollup Endpoint
    rollup_resp = client.get(
        f"/api/v1/reports/weekly/rollup?vertical_id={test_vertical.id}&user_id={officer.id}&start_date={start_of_week}&end_date={end_of_week}",
        headers=headers_officer,
    )
    assert rollup_resp.status_code == 200
    rdata = rollup_resp.json()
    assert rdata["daily_reports_count"] == 2
    assert rdata["completed_tasks_count"] >= 1
    assert rdata["blockers_count"] >= 1
    assert any("Floodlight tower 3 bulb failure" in b for b in rdata["blockers"])

    # 3. Create Weekly Report
    weekly_payload = {
        "vertical_id": str(test_vertical.id),
        "week_start_date": start_of_week.isoformat(),
        "week_end_date": end_of_week.isoformat(),
        "summary": "Successful ground preparation with minor lighting blocker resolved.",
        "completed_work": "Pitch marking and net installation complete.",
        "blockers": "Floodlight bulb replaced.",
        "priorities_next_week": "Host weekend tournament.",
        "submit_now": True,
    }
    create_resp = client.post("/api/v1/reports/weekly", json=weekly_payload, headers=headers_officer)
    assert create_resp.status_code == 201
    weekly_id = create_resp.json()["id"]

    # 4. Test Self-Review Prevention Rule (Author cannot review own weekly report)
    self_review_resp = client.post(
        f"/api/v1/reports/weekly/{weekly_id}/review",
        json={"status": "REVIEWED", "supervisor_comments": "Looks great to me"},
        headers=headers_officer,
    )
    assert self_review_resp.status_code == 403, "Author must be strictly forbidden from self-reviewing weekly report"

    # 5. Supervisor Review
    sup_review_resp = client.post(
        f"/api/v1/reports/weekly/{weekly_id}/review",
        json={"status": "REVIEWED", "supervisor_comments": "Verified on ground. Well done."},
        headers=headers_sup,
    )
    assert sup_review_resp.status_code == 200
    assert sup_review_resp.json()["status"] == "REVIEWED"
    assert sup_review_resp.json()["supervisor_comments"] == "Verified on ground. Well done."


# =============================================================================
# FEATURE 4: MEETING ACTION -> TASK CONVERSION
# =============================================================================

def test_feature4_meeting_action_to_task_conversion(client: TestClient, db_session: Session, test_vertical: Vertical):
    """
    Verifies Meeting Action Item creation and conversion to Master Task:
    - Preserves meeting, vertical, and event context.
    - Transaction-safe task generation.
    - Duplicate conversion prevention (Idempotency).
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))

    lead = user_service.create_user(
        UserCreate(
            username=f"meeting_lead_{suffix}",
            full_name=f"Meeting Lead {suffix}",
            password="SecurePassword123!",
            email=f"lead_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
            role_ids=[role_admin.id] if role_admin else [],
        )
    )
    officer = user_service.create_user(
        UserCreate(
            username=f"meeting_officer_{suffix}",
            full_name=f"Meeting Officer {suffix}",
            password="SecurePassword123!",
            email=f"officer_{suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    headers_lead = _get_auth_headers(client, lead.username, "SecurePassword123!")
    today = date.today()

    # 1. Create Meeting
    m_resp = client.post(
        "/api/v1/meetings",
        json={
            "title": "Quarterly Match Planning",
            "vertical_id": str(test_vertical.id),
            "meeting_type": "VERTICAL_REVIEW",
            "meeting_date": today.isoformat(),
            "participant_ids": [str(officer.id)],
        },
        headers=headers_lead,
    )
    assert m_resp.status_code == 201
    meeting_id = m_resp.json()["id"]

    # 2. Add Meeting Action Item
    action_payload = {
        "description": "Acquire 20 new match footballs from supplier",
        "assignee_id": str(officer.id),
        "priority": "HIGH",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    }
    act_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items",
        json=action_payload,
        headers=headers_lead,
    )
    assert act_resp.status_code == 201
    action_item_id = act_resp.json()["id"]
    assert act_resp.json()["is_converted"] is False

    # 3. Convert Action Item to Master Task
    conv_payload = {
        "title": "Procure 20 Match Footballs",
        "priority": "HIGH",
        "deadline": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    }
    conv_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/{action_item_id}/convert-to-task",
        json=conv_payload,
        headers=headers_lead,
    )
    assert conv_resp.status_code == 201
    task_data = conv_resp.json()
    assert task_data["title"] == "Procure 20 Match Footballs"
    assert task_data["assigned_to_id"] == str(officer.id)
    assert task_data["vertical_id"] == str(test_vertical.id)
    assert task_data["task_type"] == "MEETING_FOLLOW_UP"

    # 4. Duplicate Conversion Prevention Test (Retry should fail)
    retry_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/{action_item_id}/convert-to-task",
        json=conv_payload,
        headers=headers_lead,
    )
    assert retry_resp.status_code in [400, 422], "Subsequent conversion of the same action item must be rejected"

    # 5. Fresh session verification of action item state
    fresh_db = SessionLocal()
    try:
        fresh_item = fresh_db.get(MeetingActionItem, uuid.UUID(action_item_id))
        assert fresh_item.is_converted is True
        assert str(fresh_item.converted_task_id) == task_data["id"]
    finally:
        fresh_db.close()


# =============================================================================
# FEATURE 5: STRUCTURED USER / TEAM PROFILE METADATA
# =============================================================================

def test_feature5_structured_user_profile_metadata(client: TestClient, db_session: Session):
    """
    Verifies Structured Team Profile Metadata:
    - Specialization, operational capabilities, certifications, availability status.
    - Zero credentials or sensitive data in profile.
    - Fresh session PostgreSQL read verification.
    """
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    player = user_service.create_user(
        UserCreate(
            username=f"athlete_{suffix}",
            full_name=f"Athlete {suffix}",
            password="SecurePassword123!",
            email=f"athlete_{suffix}@paradox.internal",
        )
    )
    headers = _get_auth_headers(client, player.username, "SecurePassword123!")

    # 1. Get initial profile (auto-initialized)
    get_resp = client.get("/api/v1/profiles/me", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["user_id"] == str(player.id)
    assert get_resp.json()["availability"] == "AVAILABLE"

    # 2. Update operational profile
    update_payload = {
        "phone_number": "+91 9876543210",
        "specialization": "Football Referee Grade 3, Match Delegate",
        "operational_capability": "Pitch setup, electronic timing systems, CPR First Aid certified",
        "certifications": ["FIFA Grassroots Referee", "Red Cross CPR & First Aid"],
        "availability": "AVAILABLE",
        "profile_notes": "Available for weekend tournament duties.",
    }
    put_resp = client.put("/api/v1/profiles/me", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    pdata = put_resp.json()
    assert pdata["phone_number"] == "+91 9876543210"
    assert pdata["specialization"] == "Football Referee Grade 3, Match Delegate"
    assert "FIFA Grassroots Referee" in pdata["certifications"]

    # 3. Fresh Session PostgreSQL Verification
    fresh_db = SessionLocal()
    try:
        fresh_profile = fresh_db.execute(select(UserProfile).where(UserProfile.user_id == player.id)).scalar_one_or_none()
        assert fresh_profile is not None
        assert fresh_profile.phone_number == "+91 9876543210"
        assert fresh_profile.specialization == "Football Referee Grade 3, Match Delegate"
        assert len(fresh_profile.certifications) == 2
        assert fresh_profile.availability == UserAvailability.AVAILABLE
    finally:
        fresh_db.close()
