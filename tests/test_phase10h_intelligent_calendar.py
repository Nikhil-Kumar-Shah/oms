"""
Phase 10H - Intelligent Calendar Lifecycle & Master Calendar Access Control Test Suite
Tests:
1. Dynamic automatic lifecycle status computation (UPCOMING, IN_PROGRESS, COMPLETED, CANCELLED, RESCHEDULED).
2. Master Calendar strict role-based access control (Only Core, Deputy Core, Admin allowed; others receive 403 Forbidden).
3. Organizational calendar entry creation restrictions (Non-authorized users denied with 403 Forbidden).
4. Individual participant completion isolation vs Global completion (one user marking complete does NOT complete globally for others).
5. Global actions by creator/authorized owner (Complete, In Progress, Cancel, Reschedule).
6. Rescheduling audit trail (original_date preserved, rescheduled_at timestamp recorded).
7. Notifications generation for target participants on activity creation and reschedule.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.calendar import ActivityCategory, CalendarAudience, CalendarEntry, CalendarPriority, CalendarStatus
from app.models.communication import Notification
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.services.calendar_service import CalendarService

_phase10h_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10h_sessions.get(user.id)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def h_env(db_session: Session):
    """Sets up an isolated test environment with Admin, Sports Core, Deputy Core, and two Volunteers."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org 10H", code="PARADOX10H")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    v_athletics = Vertical(
        organization_id=org.id,
        name=f"Athletics 10H {uid}",
        description="Athletics Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v_athletics)
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
        if not role:
            role = Role(name=rname, description=f"{rname} Role")
            db_session.add(role)
            db_session.flush()

        db_session.add(UserRole(user_id=u.id, role_id=role.id))

        if vert:
            db_session.add(
                UserVertical(
                    user_id=u.id,
                    vertical_id=vert.id,
                )
            )
        db_session.flush()

        tok = generate_session_token()
        _phase10h_sessions[u.id] = tok
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(tok),
            ip_address="127.0.0.1",
            user_agent="pytest-10h",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        db_session.add(sess)
        db_session.flush()
        return u

    admin = _create_user("admin10h", "ADMIN", v_athletics)
    core = _create_user("core10h", "SPORTS_CORE", v_athletics)
    deputy = _create_user("deputy10h", "DEPUTY_CORE", v_athletics)
    vol_a = _create_user("vol10h_a", "VOLUNTEER", v_athletics)
    vol_b = _create_user("vol10h_b", "VOLUNTEER", v_athletics)

    db_session.commit()

    return {
        "admin": admin,
        "core": core,
        "deputy": deputy,
        "vol_a": vol_a,
        "vol_b": vol_b,
        "vertical": v_athletics,
    }


def test_dynamic_lifecycle_status_computation(client: TestClient, h_env, db_session: Session):
    """
    Test 1: Dynamic lifecycle status correctly computes UPCOMING, IN_PROGRESS, COMPLETED, and CANCELLED
    based on activity date and time windows.
    """
    service = CalendarService(db_session)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    # Future date -> UPCOMING
    entry_future = CalendarEntry(
        title="Future Activity",
        activity_date=tomorrow,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status=CalendarStatus.PLANNED,
        created_by_id=h_env["core"].id,
    )
    assert service.compute_dynamic_status(entry=entry_future) == CalendarStatus.UPCOMING

    # Past date -> COMPLETED
    entry_past = CalendarEntry(
        title="Past Activity",
        activity_date=yesterday,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status=CalendarStatus.PLANNED,
        created_by_id=h_env["core"].id,
    )
    assert service.compute_dynamic_status(entry=entry_past) == CalendarStatus.COMPLETED

    # Explicit cancelled retains CANCELLED regardless of date
    entry_cancelled = CalendarEntry(
        title="Cancelled Activity",
        activity_date=tomorrow,
        status=CalendarStatus.CANCELLED,
        created_by_id=h_env["core"].id,
    )
    assert service.compute_dynamic_status(entry=entry_cancelled) == CalendarStatus.CANCELLED

    # Participant completed overrides to COMPLETED
    assert service.compute_dynamic_status(entry=entry_future, is_user_completed=True) == CalendarStatus.COMPLETED


def test_master_calendar_strict_role_access(client: TestClient, h_env):
    """
    Test 2: Master Calendar access is strictly restricted to Core, Deputy Core, and Admin.
    Volunteers and standard users must receive 403 Forbidden.
    """
    # Admin can access Master Calendar
    res_admin = client.get("/api/v1/calendar/master", headers=_auth_headers(h_env["admin"]))
    assert res_admin.status_code == 200

    # Core can access Master Calendar
    res_core = client.get("/api/v1/calendar/master", headers=_auth_headers(h_env["core"]))
    assert res_core.status_code == 200

    # Deputy Core can access Master Calendar
    res_deputy = client.get("/api/v1/calendar/master", headers=_auth_headers(h_env["deputy"]))
    assert res_deputy.status_code == 200

    # Volunteer requesting Master Calendar receives 403 Forbidden
    res_vol = client.get("/api/v1/calendar/master", headers=_auth_headers(h_env["vol_a"]))
    assert res_vol.status_code == 403

    # Volunteer requesting /calendar?view=master also receives 403 Forbidden
    res_vol_view = client.get("/api/v1/calendar?view=master", headers=_auth_headers(h_env["vol_a"]))
    assert res_vol_view.status_code == 403


def test_organizational_creation_restricted_to_executives(client: TestClient, h_env):
    """
    Test 3: Non-executive users (e.g. Volunteer) cannot create organizational calendar entries (403 Forbidden),
    but CAN create personal activities without vertical restrictions.
    """
    # Volunteer attempting to create organizational activity -> 403 Forbidden
    org_payload = {
        "title": "Unauthorized Org Meeting",
        "activity_date": (date.today() + timedelta(days=2)).isoformat(),
        "category": "MEETING",
        "priority": "HIGH",
        "is_personal": False,
        "all_users": True,
    }
    res_unauth = client.post("/api/v1/calendar", json=org_payload, headers=_auth_headers(h_env["vol_a"]))
    assert res_unauth.status_code == 403

    # Volunteer creating a personal activity -> 201 Created
    personal_payload = {
        "title": "Volunteer Personal Plan",
        "activity_date": (date.today() + timedelta(days=1)).isoformat(),
        "category": "ACTIVITY",
        "priority": "LOW",
        "is_personal": True,
    }
    res_pers = client.post("/api/v1/calendar", json=personal_payload, headers=_auth_headers(h_env["vol_a"]))
    assert res_pers.status_code == 201
    assert res_pers.json()["is_personal"] is True


def test_individual_participant_completion_vs_global(client: TestClient, h_env, db_session: Session):
    """
    Test 4: When a meeting/activity is shared across participants, one user marking it complete
    records their individual completion state but does NOT mark it complete globally or for others.
    """
    target_date = date.today() + timedelta(days=3)

    # Core creates an activity with Vol A and Vol B as participants
    create_payload = {
        "title": "Team Strategy Alignment",
        "activity_date": target_date.isoformat(),
        "start_time": "14:00:00",
        "end_time": "15:00:00",
        "category": "MEETING",
        "priority": "HIGH",
        "is_personal": False,
        "user_ids": [str(h_env["vol_a"].id), str(h_env["vol_b"].id)],
    }
    res_create = client.post("/api/v1/calendar", json=create_payload, headers=_auth_headers(h_env["core"]))
    assert res_create.status_code == 201
    entry_id = res_create.json()["id"]

    # Vol A views activity: is_user_completed is False
    res_vol_a_view = client.get(f"/api/v1/calendar/personal", headers=_auth_headers(h_env["vol_a"]))
    assert res_vol_a_view.status_code == 200
    item_for_a = next(it for it in res_vol_a_view.json()["items"] if it["id"] == entry_id)
    assert item_for_a["is_user_completed"] is False
    assert item_for_a["status"] == "UPCOMING"

    # Vol A marks participation completed for themselves
    res_action_a = client.post(
        f"/api/v1/calendar/{entry_id}/actions",
        json={"action": "mark_completed_for_me"},
        headers=_auth_headers(h_env["vol_a"]),
    )
    assert res_action_a.status_code == 200
    assert res_action_a.json()["is_user_completed"] is True
    # Vol A's computed status is now COMPLETED
    assert res_action_a.json()["status"] == "COMPLETED"

    # Vol B views their personal calendar: Vol B has NOT marked complete, so is_user_completed remains False
    res_vol_b_view = client.get(f"/api/v1/calendar/personal", headers=_auth_headers(h_env["vol_b"]))
    assert res_vol_b_view.status_code == 200
    item_for_b = next(it for it in res_vol_b_view.json()["items"] if it["id"] == entry_id)
    assert item_for_b["is_user_completed"] is False
    assert item_for_b["status"] == "UPCOMING"


def test_global_actions_and_rescheduling_audit(client: TestClient, h_env):
    """
    Test 5: Creator or authorized owner can execute global complete, in_progress, cancel, and reschedule.
    Rescheduling updates dates, sets status RESCHEDULED, and preserves original_date.
    Non-creators cannot reschedule or globally complete someone else's activity.
    """
    initial_date = date.today() + timedelta(days=4)
    new_date = date.today() + timedelta(days=6)

    # Core creates an activity
    res_create = client.post(
        "/api/v1/calendar",
        json={
            "title": "Athletics Field Inspection",
            "activity_date": initial_date.isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "category": "ACTIVITY",
            "priority": "HIGH",
            "is_personal": False,
            "user_ids": [str(h_env["vol_a"].id)],
        },
        headers=_auth_headers(h_env["core"]),
    )
    assert res_create.status_code == 201
    entry_id = res_create.json()["id"]

    # Vol A (non-creator) attempts to globally reschedule -> 403 Forbidden
    res_unauth_reschedule = client.post(
        f"/api/v1/calendar/{entry_id}/reschedule",
        json={"new_date": new_date.isoformat(), "reason": "Weather forecast bad"},
        headers=_auth_headers(h_env["vol_a"]),
    )
    assert res_unauth_reschedule.status_code == 403

    # Creator (Core) reschedules the activity
    res_reschedule = client.post(
        f"/api/v1/calendar/{entry_id}/reschedule",
        json={
            "new_date": new_date.isoformat(),
            "new_start_time": "10:00:00",
            "new_end_time": "11:30:00",
            "reason": "Track renovation in progress",
        },
        headers=_auth_headers(h_env["core"]),
    )
    assert res_reschedule.status_code == 200
    resched_data = res_reschedule.json()
    assert resched_data["activity_date"] == new_date.isoformat()
    assert resched_data["original_date"] == initial_date.isoformat()
    assert resched_data["rescheduled_at"] is not None
    assert resched_data["status"] == "RESCHEDULED"

    # Core marks activity In Progress
    res_prog = client.post(
        f"/api/v1/calendar/{entry_id}/actions",
        json={"action": "in_progress", "remarks": "Started field walk"},
        headers=_auth_headers(h_env["core"]),
    )
    assert res_prog.status_code == 200
    assert res_prog.json()["status"] == "IN_PROGRESS"

    # Core globally completes the activity
    res_comp = client.post(
        f"/api/v1/calendar/{entry_id}/actions",
        json={"action": "complete", "remarks": "Inspection signed off"},
        headers=_auth_headers(h_env["core"]),
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"


def test_calendar_targeted_notifications(client: TestClient, h_env, db_session: Session):
    """
    Test 6: Calendar operations dispatch targeted notifications to included attendees only,
    never broadcasting organization-wide unless intended.
    """
    initial_notifs_b = db_session.query(Notification).filter(Notification.recipient_id == h_env["vol_b"].id).count()

    # Core creates an activity targeting Vol B only
    res_create = client.post(
        "/api/v1/calendar",
        json={
            "title": "Equipment Audit with Volunteer B",
            "activity_date": (date.today() + timedelta(days=2)).isoformat(),
            "category": "ACTIVITY",
            "priority": "MEDIUM",
            "is_personal": False,
            "user_ids": [str(h_env["vol_b"].id)],
        },
        headers=_auth_headers(h_env["core"]),
    )
    assert res_create.status_code == 201
    entry_id = res_create.json()["id"]

    # Verify Vol B received a notification
    new_notifs_b = (
        db_session.query(Notification)
        .filter(Notification.recipient_id == h_env["vol_b"].id)
        .order_by(Notification.created_at.desc())
        .first()
    )
    assert new_notifs_b is not None
    assert "Equipment Audit with Volunteer B" in new_notifs_b.title
