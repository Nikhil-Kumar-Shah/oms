"""
Phase 10G - Calendar & Universal Audience Integration Backend Verification Suite
Tests:
1. Master vs. Personal Calendar security separation (403 for unauthorized users).
2. Personal activity creation without vertical division by standard users.
3. Personal activity isolation (never exposed to other users).
4. Universal audience resolution (targeted users see entry, untargeted do not).
5. Dynamic real-time task projection without database record duplication.
6. Real-time synchronization when task status/deadline updates.
7. Dynamic operational meeting projection.
8. Robust validation (empty string coercion to None).
9. Object authorization on deletion.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.calendar import CalendarAudience, CalendarEntry, CalendarPriority
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, MeetingType
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User

_phase10g_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10g_sessions.get(user.id)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env(db_session: Session):
    """Sets up an isolated test environment with Admin, Coordinator, and two Volunteers."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org", code="PARADOX")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket Ops 10G {uid}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_football = Vertical(
        organization_id=org.id,
        name=f"Football Ops 10G {uid}",
        description="Football Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_cricket, v_football])
    db_session.flush()

    def _create_user(uname: str, rname: str, vert: Vertical = None) -> User:
        u = User(
            email=f"{uname}_{uid}@paradox.test",
            username=f"{uname}_{uid}",
            password_hash="fakehash",
            full_name=f"{uname.title()} User",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()

        role = db_session.query(Role).filter(Role.name == rname).first()
        if role:
            db_session.add(UserRole(user_id=u.id, role_id=role.id))

        if vert:
            db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id))

        db_session.flush()

        raw_tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(raw_tok),
            ip_address="127.0.0.1",
            user_agent="pytest",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        db_session.add(sess)
        db_session.flush()
        _phase10g_sessions[u.id] = raw_tok
        return u

    admin = _create_user(f"adm_{uid}", "ADMIN")
    coord = _create_user(f"coord_{uid}", "COORDINATOR", v_cricket)
    vol_a = _create_user(f"vola_{uid}", "VOLUNTEER", v_cricket)
    vol_b = _create_user(f"volb_{uid}", "VOLUNTEER", v_football)

    return {
        "admin": admin,
        "coord": coord,
        "vol_a": vol_a,
        "vol_b": vol_b,
        "v_cricket": v_cricket,
        "v_football": v_football,
    }


def test_master_calendar_security_separation(client: TestClient, env: dict):
    """
    Test 1 & 7: Master Calendar access is permission-based.
    Unauthorized users receive 403 Forbidden on ?view=master and /calendar/master.
    Authorized users (Admin/Sports Core) receive 200 OK.
    """
    vol_a = env["vol_a"]
    admin = env["admin"]

    # Volunteer attempts to access Master Calendar via query param -> 403
    resp_query = client.get("/api/v1/calendar?view=master", headers=_auth_headers(vol_a))
    assert resp_query.status_code == 403, f"Expected 403, got {resp_query.status_code}: {resp_query.text}"

    # Volunteer attempts to access Master Calendar via direct endpoint -> 403
    resp_direct = client.get("/api/v1/calendar/master", headers=_auth_headers(vol_a))
    assert resp_direct.status_code == 403, f"Expected 403, got {resp_direct.status_code}: {resp_direct.text}"

    # Admin accesses Master Calendar -> 200 OK
    resp_admin_query = client.get("/api/v1/calendar?view=master", headers=_auth_headers(admin))
    assert resp_admin_query.status_code == 200
    assert "items" in resp_admin_query.json()

    resp_admin_direct = client.get("/api/v1/calendar/master", headers=_auth_headers(admin))
    assert resp_admin_direct.status_code == 200
    assert "items" in resp_admin_direct.json()


def test_personal_calendar_accessible_to_all(client: TestClient, env: dict):
    """
    Test 1: Every authenticated user has their own personal calendar.
    """
    vol_a = env["vol_a"]
    resp = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a))
    assert resp.status_code == 200
    assert "items" in resp.json()

    resp_direct = client.get("/api/v1/calendar/personal", headers=_auth_headers(vol_a))
    assert resp_direct.status_code == 200
    assert "items" in resp_direct.json()


def test_create_personal_activity_without_vertical_and_isolation(client: TestClient, env: dict):
    """
    Test 2, 3 & 6:
    - Volunteer creates personal activity (no vertical division required).
    - Visible only in their personal calendar.
    - Completely invisible to other volunteers.
    - Direct access by other volunteers returns 403 Forbidden.
    """
    vol_a = env["vol_a"]
    vol_b = env["vol_b"]

    payload = {
        "title": "Doctor Appointment & Medical Checkup",
        "description": "Private appointment during the afternoon",
        "activity_date": (date.today() + timedelta(days=2)).isoformat(),
        "start_time": "14:00:00",
        "end_time": "15:30:00",
        "category": "ACTIVITY",
        "priority": "LOW",
        "is_personal": True,
        "vertical_id": None,  # No vertical forced
    }

    create_resp = client.post("/api/v1/calendar", json=payload, headers=_auth_headers(vol_a))
    assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
    created_item = create_resp.json()
    entry_id = created_item["id"]
    assert created_item["is_personal"] is True

    # Check Volunteer A's personal calendar
    list_a = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a)).json()
    assert any(it["id"] == entry_id for it in list_a["items"]), "Created entry must appear in Vol A calendar"

    # Check Volunteer B's personal calendar -> must NOT be present
    list_b = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_b)).json()
    assert not any(it["id"] == entry_id for it in list_b["items"]), "Private entry must not leak to Vol B"

    # Direct UUID probing by Volunteer B -> 403 Forbidden
    probe_resp = client.get(f"/api/v1/calendar/{entry_id}", headers=_auth_headers(vol_b))
    assert probe_resp.status_code == 403, f"Expected 403 on direct UUID probing, got {probe_resp.status_code}"


def test_validation_empty_strings_coerced_to_none(client: TestClient, env: dict):
    """
    Test 10: Frontend payload empty strings "" for optional fields must not cause
    schema mismatch or 422 errors.
    """
    vol_a = env["vol_a"]

    payload = {
        "title": "Gym & Training Session",
        "description": "",  # empty string
        "activity_date": (date.today() + timedelta(days=3)).isoformat(),
        "start_time": None,
        "end_time": None,
        "category": "ACTIVITY",
        "priority": "MEDIUM",
        "is_personal": True,
        "remarks": "",  # empty string
        "resource_link": "",  # empty string
    }

    resp = client.post("/api/v1/calendar", json=payload, headers=_auth_headers(vol_a))
    assert resp.status_code == 201, f"Validation failed on empty strings: {resp.text}"
    data = resp.json()
    assert data["description"] is None
    assert data["remarks"] is None
    assert data["resource_link"] is None


def test_automatic_task_projection_and_real_time_sync(client: TestClient, env: dict, db_session: Session):
    """
    Test 4 & 5:
    - Assigned task with deadline automatically appears in calendar with entity_type="TASK".
    - Zero duplicate records created in calendar_entries.
    - When task status is updated to COMPLETED or deadline is rescheduled,
      the calendar immediately reflects the change in real-time.
    """
    vol_a = env["vol_a"]
    coord = env["coord"]
    v_cricket = env["v_cricket"]

    deadline_dt = datetime.now(timezone.utc) + timedelta(days=5)
    task = Task(
        title="Prepare Cricket Pitch Grounds",
        description="Roll and mark the 22-yard pitch",
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        health=TaskHealth.ON_TRACK,
        status=TaskStatus.IN_PROGRESS,
        vertical_id=v_cricket.id,
        assigned_to_id=vol_a.id,
        assigned_by_id=coord.id,
        deadline=deadline_dt,
    )
    db_session.add(task)
    db_session.flush()

    # Query Volunteer A's calendar
    cal_resp = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a))
    assert cal_resp.status_code == 200
    items = cal_resp.json()["items"]

    task_cal_item = next((it for it in items if it["entity_type"] == "TASK" and it["entity_id"] == str(task.id)), None)
    assert task_cal_item is not None, "Task must automatically project onto assignee's calendar"
    assert task_cal_item["status"] == "IN_PROGRESS"
    assert task_cal_item["activity_date"] == deadline_dt.date().isoformat()
    assert "/tasks/" in task_cal_item["resource_link"]

    # Verify zero duplicate records in calendar_entries table
    dup_count = db_session.query(CalendarEntry).filter(CalendarEntry.title == f"Task: {task.title}").count()
    assert dup_count == 0, "Task projection must not insert duplicate rows into calendar_entries"

    # Real-time synchronization: complete the task and change deadline
    new_deadline = deadline_dt + timedelta(days=2)
    task.status = TaskStatus.COMPLETED
    task.deadline = new_deadline
    db_session.flush()

    # Re-query calendar
    cal_resp_2 = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a))
    assert cal_resp_2.status_code == 200
    items_2 = cal_resp_2.json()["items"]

    updated_cal_item = next((it for it in items_2 if it["entity_type"] == "TASK" and it["entity_id"] == str(task.id)), None)
    assert updated_cal_item is not None
    assert updated_cal_item["status"] == "COMPLETED", "Status must update immediately in real-time"
    assert updated_cal_item["activity_date"] == new_deadline.date().isoformat(), "Deadline must update immediately"


def test_meeting_projection(client: TestClient, env: dict, db_session: Session):
    """
    Test 4: Operational meetings automatically project to attendees' personal calendars.
    """
    vol_a = env["vol_a"]
    coord = env["coord"]
    v_cricket = env["v_cricket"]

    meeting_date = date.today() + timedelta(days=4)
    meeting = Meeting(
        title="Weekly Ground Briefing",
        description="Discuss volunteer shifts",
        organizer_id=coord.id,
        vertical_id=v_cricket.id,
        meeting_type=MeetingType.EVENT_BRIEFING,
        status=MeetingStatus.SCHEDULED,
        meeting_date=meeting_date,
    )
    db_session.add(meeting)
    db_session.flush()

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=vol_a.id,
    )
    db_session.add(participant)
    db_session.flush()

    # Check Volunteer A calendar
    cal_resp = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a))
    assert cal_resp.status_code == 200
    items = cal_resp.json()["items"]

    m_item = next((it for it in items if it["entity_type"] == "MEETING" and it["entity_id"] == str(meeting.id)), None)
    assert m_item is not None, "Meeting must project onto participant's calendar"
    assert m_item["activity_date"] == meeting_date.isoformat()


def test_organizational_activity_universal_audience(client: TestClient, env: dict):
    """
    Test 2: Universal audience targeting.
    Admin targets Volunteer A via user_ids.
    Volunteer A sees the activity; untargeted Volunteer B does not.
    """
    admin = env["admin"]
    vol_a = env["vol_a"]
    vol_b = env["vol_b"]

    payload = {
        "title": "Equipment Safety Induction",
        "description": "Induction session for certified volunteers",
        "activity_date": (date.today() + timedelta(days=6)).isoformat(),
        "category": "ONBOARDING",
        "priority": "HIGH",
        "is_personal": False,
        "user_ids": [str(vol_a.id)],  # Universal Audience targeting Vol A
    }

    create_resp = client.post("/api/v1/calendar", json=payload, headers=_auth_headers(admin))
    assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
    created_id = create_resp.json()["id"]

    # Vol A should see it
    cal_a = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a)).json()
    assert any(it["id"] == created_id for it in cal_a["items"]), "Targeted user A must see the entry"

    # Vol B should NOT see it
    cal_b = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_b)).json()
    assert not any(it["id"] == created_id for it in cal_b["items"]), "Untargeted user B must not see the entry"


def test_delete_personal_activity_authorization(client: TestClient, env: dict):
    """
    Test 13: Users can delete their own activities. Other users cannot.
    """
    vol_a = env["vol_a"]
    vol_b = env["vol_b"]

    # Vol A creates personal entry
    create_resp = client.post(
        "/api/v1/calendar",
        json={
            "title": "Personal Workout Session",
            "activity_date": (date.today() + timedelta(days=1)).isoformat(),
            "is_personal": True,
        },
        headers=_auth_headers(vol_a),
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # Vol B attempts to delete Vol A's entry -> 403 Forbidden
    del_b = client.delete(f"/api/v1/calendar/{entry_id}", headers=_auth_headers(vol_b))
    assert del_b.status_code == 403

    # Vol A deletes own entry -> 200 OK
    del_a = client.delete(f"/api/v1/calendar/{entry_id}", headers=_auth_headers(vol_a))
    assert del_a.status_code == 200

    # Ensure it's deleted
    cal_a = client.get("/api/v1/calendar?view=personal", headers=_auth_headers(vol_a)).json()
    assert not any(it["id"] == entry_id for it in cal_a["items"])
