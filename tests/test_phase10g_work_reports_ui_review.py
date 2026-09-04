"""
Test Suite for Phase 10G: Work Reports UI/UX & Weekly Report Review Refactor
Verifies:
1. Volunteer cannot view other volunteers' daily or weekly reports (403).
2. Coordinator can view vertical volunteers but not other verticals or superiors (403).
3. Super Coordinator can view coordinators & volunteers in vertical but not other verticals.
4. Sports Core and Deputy Core have organization-wide visibility.
5. Weekly reports response contains complete 7-day breakdown (Monday-Sunday), task list, and daily report entities.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User


@pytest.fixture
def phase10g_setup(db_session: Session):
    """Sets up an organization, two verticals, and users across hierarchy."""
    uid = uuid.uuid4().hex[:6]
    org = Organization(name="Phase10G Org", code=f"p10g-{uid}")
    db_session.add(org)
    db_session.flush()

    v_football = Vertical(organization_id=org.id, name=f"Football {uid}", status=VerticalStatus.ACTIVE)
    v_cricket = Vertical(organization_id=org.id, name=f"Cricket {uid}", status=VerticalStatus.ACTIVE)
    db_session.add_all([v_football, v_cricket])
    db_session.flush()

    # Roles
    roles = {}
    for rname in ["VOLUNTEER", "COORDINATOR", "SUPER_COORDINATOR", "DEPUTY_CORE", "SPORTS_CORE", "ADMIN"]:
        r = db_session.query(Role).filter(Role.name == rname).first()
        if not r:
            r = Role(name=rname, description=f"{rname} role")
            db_session.add(r)
            db_session.flush()
        roles[rname] = r

    def create_user_helper(username: str, role_name: str, vertical=None):
        u = User(
            username=f"{username}_{uid}",
            email=f"{username}_{uid}@example.com",
            password_hash="fakehash",
            full_name=f"User {username.title()}",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()

        db_session.add(UserRole(user_id=u.id, role_id=roles[role_name].id))
        if vertical:
            db_session.add(UserVertical(user_id=u.id, vertical_id=vertical.id, is_primary=True))
        db_session.flush()

        tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(tok),
            ip_address="127.0.0.1",
            user_agent="pytest-10g",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        db_session.add(sess)
        db_session.flush()

        return u, tok

    # Users
    u_vol1, tok_vol1 = create_user_helper("vol_fb1", "VOLUNTEER", v_football)
    u_vol2, tok_vol2 = create_user_helper("vol_fb2", "VOLUNTEER", v_football)
    u_vol_cricket, tok_vol_cricket = create_user_helper("vol_ck", "VOLUNTEER", v_cricket)
    u_coord_fb, tok_coord_fb = create_user_helper("coord_fb", "COORDINATOR", v_football)
    u_super_fb, tok_super_fb = create_user_helper("super_fb", "SUPER_COORDINATOR", v_football)
    u_super_ck, tok_super_ck = create_user_helper("super_ck", "SUPER_COORDINATOR", v_cricket)
    u_deputy, tok_deputy = create_user_helper("deputy", "DEPUTY_CORE")
    u_sports, tok_sports = create_user_helper("sports", "SPORTS_CORE")

    db_session.commit()

    return {
        "v_football": v_football,
        "v_cricket": v_cricket,
        "u_vol1": u_vol1,
        "tok_vol1": tok_vol1,
        "u_vol2": u_vol2,
        "tok_vol2": tok_vol2,
        "u_vol_cricket": u_vol_cricket,
        "tok_vol_cricket": tok_vol_cricket,
        "u_coord_fb": u_coord_fb,
        "tok_coord_fb": tok_coord_fb,
        "u_super_fb": u_super_fb,
        "tok_super_fb": tok_super_fb,
        "u_super_ck": u_super_ck,
        "tok_super_ck": tok_super_ck,
        "u_deputy": u_deputy,
        "tok_deputy": tok_deputy,
        "u_sports": u_sports,
        "tok_sports": tok_sports,
    }


def test_volunteer_cannot_view_other_volunteer_reports(client: TestClient, phase10g_setup):
    """Volunteer 1 cannot view Volunteer 2's daily or weekly report even in the same vertical."""
    tok_vol1 = phase10g_setup["tok_vol1"]
    tok_vol2 = phase10g_setup["tok_vol2"]
    u_vol2 = phase10g_setup["u_vol2"]

    # 1. Vol2 submits a daily report
    res = client.post(
        "/api/v1/reports/daily",
        headers={"Authorization": f"Bearer {tok_vol2}"},
        json={"work_summary": "Vol2 secret operational activity completed today."},
    )
    assert res.status_code == 201, res.text
    vol2_report_id = res.json()["id"]

    # 2. Vol1 tries to access Vol2's report directly via GET /daily/{id}
    res_get = client.get(
        f"/api/v1/reports/daily/{vol2_report_id}",
        headers={"Authorization": f"Bearer {tok_vol1}"},
    )
    assert res_get.status_code == 403, f"Expected 403 Forbidden, got {res_get.status_code}"

    # 3. Vol1 tries to query Vol2's weekly report via GET /weekly/current?user_id=...
    res_weekly = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol2.id}",
        headers={"Authorization": f"Bearer {tok_vol1}"},
    )
    assert res_weekly.status_code == 403, f"Expected 403 Forbidden for weekly current, got {res_weekly.status_code}"

    # 4. Vol1 tries to query Vol2's reports via GET /weekly?user_id=...
    res_list_weekly = client.get(
        f"/api/v1/reports/weekly?user_id={u_vol2.id}",
        headers={"Authorization": f"Bearer {tok_vol1}"},
    )
    assert res_list_weekly.status_code == 403, f"Expected 403 Forbidden for weekly list, got {res_list_weekly.status_code}"


def test_coordinator_vertical_scoping_and_superior_restriction(client: TestClient, phase10g_setup):
    """Coordinator can view vertical volunteer, but not other vertical volunteer or superior."""
    tok_coord_fb = phase10g_setup["tok_coord_fb"]
    u_vol1 = phase10g_setup["u_vol1"]
    u_vol_cricket = phase10g_setup["u_vol_cricket"]
    u_super_fb = phase10g_setup["u_super_fb"]

    # 1. Coordinator querying Volunteer in same vertical -> Allowed (200)
    res_ok = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol1.id}",
        headers={"Authorization": f"Bearer {tok_coord_fb}"},
    )
    assert res_ok.status_code == 200, res_ok.text
    data = res_ok.json()
    assert data["user_id"] == str(u_vol1.id)

    # 2. Coordinator querying Volunteer in different vertical -> Denied (403)
    res_diff_v = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol_cricket.id}",
        headers={"Authorization": f"Bearer {tok_coord_fb}"},
    )
    assert res_diff_v.status_code == 403, f"Expected 403 for other vertical, got {res_diff_v.status_code}"

    # 3. Coordinator querying Super Coordinator (superior) in same vertical -> Denied (403)
    res_superior = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_super_fb.id}",
        headers={"Authorization": f"Bearer {tok_coord_fb}"},
    )
    assert res_superior.status_code == 403, f"Expected 403 for superior, got {res_superior.status_code}"


def test_super_coordinator_hierarchy_permissions(client: TestClient, phase10g_setup):
    """Super Coordinator can view Coordinator and Volunteer in vertical, but not other verticals."""
    tok_super_fb = phase10g_setup["tok_super_fb"]
    u_coord_fb = phase10g_setup["u_coord_fb"]
    u_vol1 = phase10g_setup["u_vol1"]
    u_vol_cricket = phase10g_setup["u_vol_cricket"]

    # 1. Super Coordinator views Coordinator in vertical -> 200 OK
    res_coord = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_coord_fb.id}",
        headers={"Authorization": f"Bearer {tok_super_fb}"},
    )
    assert res_coord.status_code == 200, res_coord.text

    # 2. Super Coordinator views Volunteer in vertical -> 200 OK
    res_vol = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol1.id}",
        headers={"Authorization": f"Bearer {tok_super_fb}"},
    )
    assert res_vol.status_code == 200, res_vol.text

    # 3. Super Coordinator views Cricket Volunteer -> 403 Forbidden
    res_other = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol_cricket.id}",
        headers={"Authorization": f"Bearer {tok_super_fb}"},
    )
    assert res_other.status_code == 403, f"Expected 403 for other vertical, got {res_other.status_code}"


def test_sports_core_and_deputy_core_org_wide_access(client: TestClient, phase10g_setup):
    """Sports Core and Deputy Core can view all users across all verticals."""
    tok_sports = phase10g_setup["tok_sports"]
    tok_deputy = phase10g_setup["tok_deputy"]
    u_vol1 = phase10g_setup["u_vol1"]
    u_vol_cricket = phase10g_setup["u_vol_cricket"]
    u_super_fb = phase10g_setup["u_super_fb"]

    # Sports Core checks football volunteer and cricket volunteer
    res_fb = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol1.id}",
        headers={"Authorization": f"Bearer {tok_sports}"},
    )
    assert res_fb.status_code == 200, res_fb.text

    res_ck = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_vol_cricket.id}",
        headers={"Authorization": f"Bearer {tok_sports}"},
    )
    assert res_ck.status_code == 200, res_ck.text

    # Deputy Core checks Super Coordinator in Football
    res_dep = client.get(
        f"/api/v1/reports/weekly/current?user_id={u_super_fb.id}",
        headers={"Authorization": f"Bearer {tok_deputy}"},
    )
    assert res_dep.status_code == 200, res_dep.text


def test_weekly_report_contains_7_day_breakdown(client: TestClient, phase10g_setup):
    """Weekly report response contains days_reported (Monday-Sunday) and daily_reports."""
    tok_vol1 = phase10g_setup["tok_vol1"]
    u_vol1 = phase10g_setup["u_vol1"]

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    # Submit daily reports for Monday and Tuesday
    res_m = client.post(
        "/api/v1/reports/daily",
        headers={"Authorization": f"Bearer {tok_vol1}"},
        json={
            "report_date": monday.isoformat(),
            "work_summary": "Completed stadium setup on Monday.",
            "blockers": "None",
            "next_actions": "Prepare turf on Tuesday",
        },
    )
    assert res_m.status_code == 201, res_m.text

    res_t = client.post(
        "/api/v1/reports/daily",
        headers={"Authorization": f"Bearer {tok_vol1}"},
        json={
            "report_date": (monday + timedelta(days=1)).isoformat(),
            "work_summary": "Completed turf preparation on Tuesday.",
            "blockers": "Rain delayed work by 1 hour",
            "next_actions": "Equipment inspection on Wednesday",
        },
    )
    assert res_t.status_code == 201, res_t.text

    # Retrieve weekly report
    res_weekly = client.get(
        f"/api/v1/reports/weekly/current?week_start={monday.isoformat()}",
        headers={"Authorization": f"Bearer {tok_vol1}"},
    )
    assert res_weekly.status_code == 200, res_weekly.text
    data = res_weekly.json()

    assert data["days_reported_count"] == 2
    assert len(data["days_reported"]) == 7

    # Check Monday entry
    mon_entry = data["days_reported"][0]
    assert mon_entry["day_of_week"] == "Monday"
    assert mon_entry["reported"] is True
    assert mon_entry["status"] == "SUBMITTED"

    # Check Tuesday entry
    tue_entry = data["days_reported"][1]
    assert tue_entry["day_of_week"] == "Tuesday"
    assert tue_entry["reported"] is True

    # Check Wednesday entry (not reported)
    wed_entry = data["days_reported"][2]
    assert wed_entry["day_of_week"] == "Wednesday"
    assert wed_entry["reported"] is False
    assert wed_entry["report_id"] is None

    # Check daily_reports list
    assert len(data["daily_reports"]) == 2
    summaries = [dr["work_summary"] for dr in data["daily_reports"]]
    assert any("Monday" in s for s in summaries)
    assert any("Tuesday" in s for s in summaries)
