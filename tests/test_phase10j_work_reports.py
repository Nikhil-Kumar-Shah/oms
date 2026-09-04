"""
Phase 10J: Daily Work Reports & Hierarchical Review Test Suite
Paradox Sports OMS - Acceptance & Hierarchy Verification
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport, WeeklyReport, WeeklyReportStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.session import UserSession
from app.models.user import AccountStatus, User

_phase10j_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10j_sessions[user.id]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def r_env(db_session: Session):
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org 10J", code="PARADOX10J")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    v_football = Vertical(
        organization_id=org.id,
        name=f"Football {uid}",
        description="Football Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket {uid}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_football, v_cricket])
    db_session.flush()

    def _create_user(uname: str, rname: str, vert: Vertical = None, full_name: str = None) -> User:
        u = User(
            email=f"{uname}_{uid}@paradox.test",
            username=f"{uname}_{uid}",
            password_hash="fakehash",
            full_name=full_name or f"{uname.title()} Fullname",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()

        role = db_session.query(Role).filter(Role.name == rname).first()
        if not role:
            role = Role(name=rname, description=f"{rname} Role")
            db_session.add(role)
            db_session.flush()

        db_session.add(UserRole(user_id=u.id, role_id=role.id))

        if vert:
            db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id))
        db_session.flush()

        tok = generate_session_token()
        _phase10j_sessions[u.id] = tok
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(tok),
            ip_address="127.0.0.1",
            user_agent="pytest-10j",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        db_session.add(sess)
        db_session.flush()
        return u

    admin = _create_user("admin10j", "ADMIN", v_football)
    sports_core = _create_user("core10j", "SPORTS_CORE", v_football)
    deputy_core = _create_user("deputy10j", "DEPUTY_CORE", v_football)
    super_fb = _create_user("super_fb_10j", "SUPER_COORDINATOR", v_football)
    coord_fb = _create_user("coord_fb_10j", "COORDINATOR", v_football)
    coord_cricket = _create_user("coord_ck_10j", "COORDINATOR", v_cricket)
    vol_fb = _create_user("vol_fb_10j", "VOLUNTEER", v_football)
    event_team = _create_user("evteam10j", "EVENT_TEAM", v_football)

    # Create assigned tasks for Volunteer
    t1 = Task(
        title=f"Setup Goalposts {uid}",
        vertical_id=v_football.id,
        assigned_to_id=vol_fb.id,
        assigned_by_id=admin.id,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )
    t2 = Task(
        title=f"Inventory Footballs {uid}",
        vertical_id=v_football.id,
        assigned_to_id=vol_fb.id,
        assigned_by_id=admin.id,
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    return {
        "admin": admin,
        "sports_core": sports_core,
        "deputy_core": deputy_core,
        "super_fb": super_fb,
        "coord_fb": coord_fb,
        "coord_cricket": coord_cricket,
        "vol_fb": vol_fb,
        "event_team": event_team,
        "v_football": v_football,
        "v_cricket": v_cricket,
        "task_1": t1,
        "task_2": t2,
    }


def test_auto_derived_identity_and_multi_task_reporting(client: TestClient, r_env):
    """
    Verifies that a daily report auto-derives the author, role, vertical, and report date,
    and correctly associates multiple assigned tasks with per-task progress notes.
    """
    vol = r_env["vol_fb"]
    t1 = r_env["task_1"]
    t2 = r_env["task_2"]

    headers = _auth_headers(vol)
    payload = {
        "work_summary": "Completed morning equipment check and goalpost setup.",
        "tasks": [
            {"task_id": str(t1.id), "progress_notes": "Ground anchors fixed securely."},
            {"task_id": str(t2.id), "progress_notes": "All 15 match balls inflated and inspected."},
        ],
        "blockers": "Slight rain in the early morning.",
        "next_actions": "Prepare team line-up boards tomorrow.",
        "evidence_links": "https://paradox.test/evidence/day1",
    }

    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["user_id"] == str(vol.id)
    assert data["vertical_id"] == str(r_env["v_football"].id)
    assert data["report_date"] == date.today().isoformat()
    assert data["status"] == "SUBMITTED"
    assert len(data["tasks"]) == 2
    task_ids = {t["task_id"] for t in data["tasks"]}
    assert str(t1.id) in task_ids
    assert str(t2.id) in task_ids


def test_volunteer_to_coordinator_review_hierarchy(client: TestClient, r_env):
    """
    Volunteer submits a report ->
    Coordinator of same vertical sees it in supervisor queue and can review it.
    Coordinator of different vertical CANNOT review it (403 Forbidden).
    """
    vol = r_env["vol_fb"]
    coord_fb = r_env["coord_fb"]
    coord_ck = r_env["coord_cricket"]

    # 1. Volunteer submits report
    headers_vol = _auth_headers(vol)
    payload = {
        "work_summary": "Marked boundaries and assisted football players.",
    }
    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers_vol)
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    # 2. Football Coordinator checks review queue
    headers_fb = _auth_headers(coord_fb)
    q_resp = client.get("/api/v1/reports/review-queue", headers=headers_fb)
    assert q_resp.status_code == 200
    queue_items = q_resp.json()["items"]
    assert any(it["id"] == report_id for it in queue_items)

    # 3. Cricket Coordinator tries to review Football report -> 403 Forbidden
    headers_ck = _auth_headers(coord_ck)
    rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Looks good from Cricket"},
        headers=headers_ck,
    )
    assert rev_resp.status_code == 403

    # 4. Football Coordinator reviews and approves
    rev_resp_fb = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Great work on the pitch today!"},
        headers=headers_fb,
    )
    assert rev_resp_fb.status_code == 200
    assert rev_resp_fb.json()["status"] == "REVIEWED"
    assert rev_resp_fb.json()["reviewed_by_id"] == str(coord_fb.id)


def test_coordinator_to_super_coordinator_hierarchy(client: TestClient, r_env):
    """
    Coordinator submits a report ->
    Super Coordinator of same vertical sees it in supervisor queue and approves.
    """
    coord_fb = r_env["coord_fb"]
    super_fb = r_env["super_fb"]

    headers_coord = _auth_headers(coord_fb)
    resp = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Supervised volunteer pitch preparation and match schedules."},
        headers=headers_coord,
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    headers_super = _auth_headers(super_fb)
    q_resp = client.get("/api/v1/reports/review-queue", headers=headers_super)
    assert q_resp.status_code == 200
    assert any(it["id"] == report_id for it in q_resp.json()["items"])

    rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Coordinator report approved by Super Coordinator."},
        headers=headers_super,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "REVIEWED"


def test_super_coordinator_to_core_hierarchy(client: TestClient, r_env):
    """
    Super Coordinator submits -> Deputy Core and Sports Core can both review.
    """
    super_fb = r_env["super_fb"]
    deputy = r_env["deputy_core"]

    headers_super = _auth_headers(super_fb)
    resp = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Organized vertical tournament logistics across 4 pitches."},
        headers=headers_super,
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    headers_deputy = _auth_headers(deputy)
    q_resp = client.get("/api/v1/reports/review-queue", headers=headers_deputy)
    assert q_resp.status_code == 200
    assert any(it["id"] == report_id for it in q_resp.json()["items"])

    rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Reviewed by Deputy Core."},
        headers=headers_deputy,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "REVIEWED"


def test_core_and_deputy_core_cross_review(client: TestClient, r_env):
    """
    Sports Core submits -> Deputy Core reviews.
    Deputy Core submits -> Sports Core reviews.
    """
    sports_core = r_env["sports_core"]
    deputy = r_env["deputy_core"]

    # 1. Sports Core submits -> Deputy Core reviews
    resp1 = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Overseeing federation approvals and university sports budget."},
        headers=_auth_headers(sports_core),
    )
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    rev1 = client.post(
        f"/api/v1/reports/daily/{id1}/review",
        json={"status": "REVIEWED", "review_comments": "Deputy Core approval."},
        headers=_auth_headers(deputy),
    )
    assert rev1.status_code == 200
    assert rev1.json()["status"] == "REVIEWED"

    # 2. Deputy Core submits -> Sports Core reviews
    resp2 = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Coordinated medical team deployments across all verticals."},
        headers=_auth_headers(deputy),
    )
    assert resp2.status_code == 201
    id2 = resp2.json()["id"]

    rev2 = client.post(
        f"/api/v1/reports/daily/{id2}/review",
        json={"status": "REVIEWED", "review_comments": "Sports Core approval."},
        headers=_auth_headers(sports_core),
    )
    assert rev2.status_code == 200
    assert rev2.json()["status"] == "REVIEWED"


def test_self_review_strictly_forbidden(client: TestClient, r_env):
    """Verifies that an author cannot review their own report."""
    coord = r_env["coord_fb"]
    headers = _auth_headers(coord)

    resp = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Testing self review restriction."},
        headers=headers,
    )
    assert resp.status_code == 201
    rep_id = resp.json()["id"]

    rev = client.post(
        f"/api/v1/reports/daily/{rep_id}/review",
        json={"status": "REVIEWED", "review_comments": "Attempting self-approval."},
        headers=headers,
    )
    assert rev.status_code == 403


def test_return_for_correction_and_resubmit(client: TestClient, r_env):
    """
    Supervisor returns report for correction with comments ->
    Author sees RETURNED status ->
    Author updates and resubmits ->
    Report status becomes SUBMITTED again.
    """
    vol = r_env["vol_fb"]
    coord = r_env["coord_fb"]

    # 1. Vol submits incomplete report
    resp = client.post(
        "/api/v1/reports/daily",
        json={"work_summary": "Did some minor work."},
        headers=_auth_headers(vol),
    )
    assert resp.status_code == 201
    rep_id = resp.json()["id"]

    # 2. Coordinator returns report
    ret_resp = client.post(
        f"/api/v1/reports/daily/{rep_id}/review",
        json={"status": "RETURNED", "review_comments": "Please provide more detail on pitch maintenance."},
        headers=_auth_headers(coord),
    )
    assert ret_resp.status_code == 200
    assert ret_resp.json()["status"] == "RETURNED"

    # 3. Volunteer edits and resubmits
    resub_resp = client.post(
        f"/api/v1/reports/daily/{rep_id}/resubmit",
        json={"work_summary": "Cleaned the equipment room and inspected goal netting thoroughly."},
        headers=_auth_headers(vol),
    )
    assert resub_resp.status_code == 200
    assert resub_resp.json()["status"] == "SUBMITTED"
    assert "equipment room" in resub_resp.json()["work_summary"]


def test_automatic_weekly_report_generation(client: TestClient, r_env):
    """
    Verifies that calling /reports/weekly/current automatically aggregates
    the past 7 days of daily reports into a weekly report summary.
    """
    vol = r_env["vol_fb"]
    headers = _auth_headers(vol)

    # Query current weekly report
    w_resp = client.get("/api/v1/reports/weekly/current", headers=headers)
    assert w_resp.status_code == 200
    w_data = w_resp.json()

    assert w_data["user_id"] == str(vol.id)
    assert w_data["vertical_id"] == str(r_env["v_football"].id)
    assert w_data["status"] == "SUBMITTED"
    assert "summary" in w_data


def test_empty_optional_fields_coercion(client: TestClient, r_env):
    """
    Verifies that sending empty strings for optional fields is coerced to None/null
    without triggering 422 payload errors.
    """
    vol = r_env["vol_fb"]
    headers = _auth_headers(vol)

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "report_date": yesterday,
        "work_summary": "Cleaned up training cones after practice sessions.",
        "blockers": "",
        "issues": "",
        "next_actions": "",
        "evidence_links": "",
        "tasks_completed": "",
        "vertical_id": "",
    }

    resp = client.post("/api/v1/reports/daily", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["blockers"] is None
    assert data["issues"] is None
    assert data["next_actions"] is None
    assert data["evidence_links"] is None
