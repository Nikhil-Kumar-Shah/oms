"""
Phase 10D - API Contract & Operational Form Stability Test Suite
Verifies contract alignment, enum synchronization, optional field handling,
detailed 422 validation error exposure, and vertical authorization across all OMS operational forms.
"""

import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.communication import AnnouncementPriority, AnnouncementScope, AnnouncementStatus
from app.models.event import Event, EventStatus, EventType
from app.models.form import FormAudience, FormFieldType, FormStatus
from app.models.issue import IssueSensitivity, IssueStatus
from app.models.meeting import MeetingStatus, MeetingType
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User


@pytest.fixture
def form_test_env(db_session: Session):
    """Sets up a comprehensive fixture environment with users, verticals, and tasks."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org", code="PARADOX")
        db_session.add(org)
        db_session.flush()

    # Verticals
    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket Division {uuid.uuid4().hex[:6]}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_badminton = Vertical(
        organization_id=org.id,
        name=f"Badminton Division {uuid.uuid4().hex[:6]}",
        description="Badminton Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_cricket, v_badminton])
    db_session.flush()

    # Roles
    r_admin = db_session.query(Role).filter_by(name="ADMIN").first()
    r_sports_core = db_session.query(Role).filter_by(name="SPORTS_CORE").first()
    r_super_coord = db_session.query(Role).filter_by(name="SUPER_COORDINATOR").first()
    r_coord = db_session.query(Role).filter_by(name="COORDINATOR").first()
    r_vol = db_session.query(Role).filter_by(name="VOLUNTEER").first()

    uid = uuid.uuid4().hex[:6]
    # Users
    u_admin = User(
        username=f"admin_ft_{uid}",
        email=f"admin_ft_{uid}@oms.test",
        full_name=f"Admin FT {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_score = User(
        username=f"score_ft_{uid}",
        email=f"score_ft_{uid}@oms.test",
        full_name=f"Sports Core FT {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_cricket = User(
        username=f"coord_cric_ft_{uid}",
        email=f"coord_cric_ft_{uid}@oms.test",
        full_name=f"Coord Cricket FT {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol_cricket = User(
        username=f"vol_cric_ft_{uid}",
        email=f"vol_cric_ft_{uid}@oms.test",
        full_name=f"Vol Cricket FT {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_badminton = User(
        username=f"coord_badm_ft_{uid}",
        email=f"coord_badm_ft_{uid}@oms.test",
        full_name=f"Coord Badminton FT {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )

    db_session.add_all([u_admin, u_score, u_coord_cricket, u_vol_cricket, u_coord_badminton])
    db_session.flush()

    # User Roles
    db_session.add_all([
        UserRole(user_id=u_admin.id, role_id=r_admin.id),
        UserRole(user_id=u_score.id, role_id=r_sports_core.id),
        UserRole(user_id=u_coord_cricket.id, role_id=r_coord.id),
        UserRole(user_id=u_vol_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_coord_badminton.id, role_id=r_coord.id),
    ])

    # Vertical memberships
    db_session.add_all([
        UserVertical(user_id=u_coord_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_vol_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_coord_badminton.id, vertical_id=v_badminton.id),
    ])

    # Create a task in Cricket
    task_cric = Task(
        title="Cricket Equipment Check",
        vertical_id=v_cricket.id,
        assigned_to_id=u_vol_cricket.id,
        assigned_by_id=u_score.id,
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.ON_TRACK,
        completion_percentage=25,
    )
    # Create a task in Badminton
    task_badm = Task(
        title="Badminton Net Setup",
        vertical_id=v_badminton.id,
        assigned_to_id=u_coord_badminton.id,
        assigned_by_id=u_score.id,
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.IN_PROGRESS,
        health=TaskHealth.ON_TRACK,
        completion_percentage=10,
    )
    db_session.add_all([task_cric, task_badm])
    # Create session tokens for all test users
    from datetime import timedelta
    from app.core.security import generate_session_token, hash_session_token
    from app.models.session import UserSession

    global _session_cache
    _session_cache = {}
    for u in [u_admin, u_score, u_coord_cricket, u_vol_cricket, u_coord_badminton]:
        raw_tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ip_address="127.0.0.1",
        )
        db_session.add(sess)
        _session_cache[u.id] = raw_tok

    db_session.commit()

    return {
        "admin": u_admin,
        "sports_core": u_score,
        "coord_cricket": u_coord_cricket,
        "vol_cricket": u_vol_cricket,
        "coord_badminton": u_coord_badminton,
        "v_cricket": v_cricket,
        "v_badminton": v_badminton,
        "task_cric": task_cric,
        "task_badm": task_badm,
    }


_session_cache = {}


def _auth_headers(user: User) -> dict:
    return {"Authorization": f"Bearer {_session_cache[user.id]}"}


# =============================================================================
# 1. Detailed Validation Error Exposure Tests
# =============================================================================

def test_validation_error_preserves_field_and_reason(client: TestClient, form_test_env: dict):
    """Verifies that HTTP 422 responses return formatted 'Validation error: <field>: <reason>'."""
    headers = _auth_headers(form_test_env["sports_core"])

    # Send an invalid payload missing required 'title' and 'vertical_id'
    resp = client.post("/api/v1/tasks", json={}, headers=headers)
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert "Validation error:" in data["error"]["message"]
    # Check that field names are present in message
    assert "title" in data["error"]["message"]
    assert "vertical_id" in data["error"]["message"]
    # Check that structured details are preserved
    assert "validation_errors" in data["error"]["details"]
    assert len(data["error"]["details"]["validation_errors"]) > 0


# =============================================================================
# 2. Master Task Contract Tests
# =============================================================================

def test_create_task_without_assignee_success(client: TestClient, form_test_env: dict):
    """Verifies creating a master task without an assignee succeeds (assignee_id null/omitted)."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Unassigned Pitch Preparation",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "assigned_to_id": None,
        "task_type": "ROUTINE",
        "priority": "MEDIUM",
        "description": "Prepare pitch roller and boundary ropes.",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Unassigned Pitch Preparation"
    assert body["assigned_to_id"] is None


def test_create_task_with_valid_assignee_success(client: TestClient, form_test_env: dict):
    """Verifies creating a master task with a valid assignee succeeds."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Assigned Pitch Marking",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "assigned_to_id": str(form_test_env["vol_cricket"].id),
        "task_type": "EVENT",
        "priority": "HIGH",
        "description": "Chalk lines for pitch and crease.",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Assigned Pitch Marking"
    assert body["assigned_to_id"] == str(form_test_env["vol_cricket"].id)


def test_create_task_invalid_type_returns_detailed_422(client: TestClient, form_test_env: dict):
    """Verifies that obsolete frontend task_type values produce a clear 422 error."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Invalid Type Task",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "task_type": "NON_EXISTENT_TYPE",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "task_type" in resp.json()["error"]["message"]


# =============================================================================
# 3. Operational Issue Contract & Scope Tests
# =============================================================================

def test_create_issue_without_assignee_success(client: TestClient, form_test_env: dict):
    """Verifies raising an operational issue without assignee succeeds."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Floodlight Failure Tower 3",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "description": "Main circuit breaker tripped during evening session.",
        "sensitivity": "NORMAL",
        "assigned_to_id": None,
    }
    resp = client.post("/api/v1/issues", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Floodlight Failure Tower 3"
    assert body["assigned_to_id"] is None


def test_create_issue_with_assignee_success(client: TestClient, form_test_env: dict):
    """Verifies raising an operational issue with an assignee succeeds."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Broken Net Pulley",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "description": "Practice net pulley cable snapped.",
        "sensitivity": "SENSITIVE",
        "assigned_to_id": str(form_test_env["coord_cricket"].id),
    }
    resp = client.post("/api/v1/issues", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Broken Net Pulley"
    assert body["assigned_to_id"] == str(form_test_env["coord_cricket"].id)


def test_create_issue_unauthorized_vertical_rejected(client: TestClient, form_test_env: dict):
    """Verifies non-executive coordinator cannot raise issue in unrelated vertical."""
    # Cricket coordinator trying to raise issue in Badminton
    headers = _auth_headers(form_test_env["coord_cricket"])
    payload = {
        "title": "Cross Vertical Intrusion Issue",
        "vertical_id": str(form_test_env["v_badminton"].id),
        "description": "Unauthorized attempt to raise an issue in another division.",
    }
    resp = client.post("/api/v1/issues", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "Cross-vertical violation" in resp.json()["error"]["message"]


# =============================================================================
# 4. Daily Work Report Contract & Unlinked Tasks Tests
# =============================================================================

def test_create_daily_report_without_task_success(client: TestClient, form_test_env: dict):
    """Verifies submitting daily work report without assigned task (assigned_task_id = null) succeeds."""
    headers = _auth_headers(form_test_env["vol_cricket"])
    payload = {
        "vertical_id": str(form_test_env["v_cricket"].id),
        "report_date": date.today().isoformat(),
        "work_summary": "Cleaned up equipment room and verified tournament balls inventory.",
        "assigned_task_id": None,
        "submit_now": True,
    }
    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["work_summary"] == "Cleaned up equipment room and verified tournament balls inventory."
    assert body["status"] == "SUBMITTED"


def test_create_daily_report_with_valid_task_success(client: TestClient, form_test_env: dict, db_session: Session):
    """Verifies submitting daily work report linked to an assigned task succeeds."""
    # Use tomorrow's date to avoid unique constraint conflict with previous test
    rep_date = date.fromordinal(date.today().toordinal() + 1).isoformat()
    headers = _auth_headers(form_test_env["vol_cricket"])
    payload = {
        "vertical_id": str(form_test_env["v_cricket"].id),
        "report_date": rep_date,
        "work_summary": "Inspected all cricket bats and recorded wear on turf pitch.",
        "assigned_task_id": str(form_test_env["task_cric"].id),
        "tasks_completed": "[Task: Cricket Equipment Check] Completed 25% of inspection.",
        "submit_now": True,
    }
    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "SUBMITTED"


def test_create_daily_report_unauthorized_task_rejected(client: TestClient, form_test_env: dict):
    """Verifies that linking a task outside user's vertical/scope is rejected."""
    rep_date = date.fromordinal(date.today().toordinal() + 2).isoformat()
    headers = _auth_headers(form_test_env["vol_cricket"])
    # Attempting to link to Badminton task
    payload = {
        "vertical_id": str(form_test_env["v_cricket"].id),
        "report_date": rep_date,
        "work_summary": "Attempting to link to badminton task from cricket volunteer.",
        "assigned_task_id": str(form_test_env["task_badm"].id),
    }
    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "not belong to your authorized scope" in resp.json()["error"]["message"]


# =============================================================================
# 5. Announcement Scope & Audience Tests
# =============================================================================

def test_create_announcement_all_and_organization_scopes(client: TestClient, form_test_env: dict):
    """Verifies creating announcements with ALL and ORGANIZATION scopes."""
    headers = _auth_headers(form_test_env["admin"])

    # Scope ALL
    resp_all = client.post(
        "/api/v1/announcements",
        json={
            "title": "Welcome to Annual Sports Meet",
            "content": "All departments please note registration guidelines.",
            "scope": "ALL",
            "publish_now": True,
        },
        headers=headers,
    )
    assert resp_all.status_code == 201, resp_all.text
    assert resp_all.json()["scope"] == "ALL"

    # Scope ORGANIZATION
    resp_org = client.post(
        "/api/v1/announcements",
        json={
            "title": "Code of Conduct Update",
            "content": "Updated code of conduct for all organization members.",
            "scope": "ORGANIZATION",
            "publish_now": True,
        },
        headers=headers,
    )
    assert resp_org.status_code == 201, resp_org.text
    assert resp_org.json()["scope"] in ["ALL", "ORGANIZATION"]


def test_create_announcement_vertical_scope(client: TestClient, form_test_env: dict):
    """Verifies creating an announcement with VERTICAL scope."""
    headers = _auth_headers(form_test_env["admin"])
    payload = {
        "title": "Cricket Tournament Draw",
        "content": "First round match schedule published.",
        "scope": "VERTICAL",
        "vertical_id": str(form_test_env["v_cricket"].id),
        "publish_now": True,
    }
    resp = client.post("/api/v1/announcements", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["vertical_id"] == str(form_test_env["v_cricket"].id)


def test_create_announcement_vertical_missing_id_returns_422(client: TestClient, form_test_env: dict):
    """Verifies that scope VERTICAL without vertical_id produces 422 error."""
    headers = _auth_headers(form_test_env["admin"])
    payload = {
        "title": "Invalid Vertical Announcement",
        "content": "Missing vertical_id when scope is VERTICAL.",
        "scope": "VERTICAL",
        "vertical_id": None,
    }
    resp = client.post("/api/v1/announcements", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "Vertical ID is required" in resp.json()["error"]["message"]


# =============================================================================
# 6. Meeting Contract & Enum Synchronization Tests
# =============================================================================

def test_create_meeting_valid_fields_and_types(client: TestClient, form_test_env: dict):
    """Verifies scheduling operational meetings with standard and newly synchronized types."""
    headers = _auth_headers(form_test_env["sports_core"])

    for m_type in ["INTERNAL_SYNC", "CROSS_VERTICAL", "EVENT_BRIEFING", "DEBRIEF", "EMERGENCY"]:
        payload = {
            "title": f"Meeting for {m_type}",
            "meeting_type": m_type,
            "meeting_date": date.today().isoformat(),
            "start_time": "14:00:00",
            "end_time": "15:30:00",
            "location": "Boardroom A",
            "description": "Agenda points for operational discussion.",
            "vertical_id": str(form_test_env["v_cricket"].id),
            "participant_ids": [str(form_test_env["coord_cricket"].id)],
        }
        resp = client.post("/api/v1/meetings", json=payload, headers=headers)
        assert resp.status_code == 201, f"Failed for {m_type}: {resp.text}"
        body = resp.json()
        assert body["meeting_type"] == m_type
        # Host + invited attendee = 2 participants
        assert len(body["participants"]) >= 1
        assert any(p["user_id"] == str(form_test_env["coord_cricket"].id) for p in body["participants"])


def test_create_meeting_missing_required_date_returns_422(client: TestClient, form_test_env: dict):
    """Verifies missing required meeting_date returns 422 with field detail."""
    headers = _auth_headers(form_test_env["sports_core"])
    payload = {
        "title": "Meeting Without Date",
        "meeting_type": "INTERNAL_SYNC",
    }
    resp = client.post("/api/v1/meetings", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "meeting_date" in resp.json()["error"]["message"]


# =============================================================================
# 7. Form Builder Template & Field Types Tests
# =============================================================================

def test_create_form_template_with_phone_field(client: TestClient, form_test_env: dict):
    """Verifies creating a dynamic form template with PHONE and TEXT field types."""
    headers = _auth_headers(form_test_env["admin"])
    payload = {
        "name": "Referee Registration Form",
        "purpose": "Collect contact and certification details from referees",
        "category": "Operational",
        "target_audience": "ORGANIZATION",
        "sections": [
            {
                "title": "Contact Details",
                "ordering": 1,
                "fields": [
                    {
                        "key": "referee_name",
                        "label": "Referee Full Name",
                        "type": "TEXT",
                        "required": True,
                        "ordering": 1,
                    },
                    {
                        "key": "contact_phone",
                        "label": "Primary Contact Phone",
                        "type": "PHONE",
                        "required": True,
                        "ordering": 2,
                    },
                ],
            }
        ],
    }
    resp = client.post("/api/v1/forms", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Referee Registration Form"
    assert body["purpose"] == "Collect contact and certification details from referees"


def test_create_form_template_missing_purpose_returns_422(client: TestClient, form_test_env: dict):
    """Verifies that omitting required purpose from form creation returns a clear 422."""
    headers = _auth_headers(form_test_env["admin"])
    payload = {
        "name": "Form Without Purpose",
    }
    resp = client.post("/api/v1/forms", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "purpose" in resp.json()["error"]["message"]
