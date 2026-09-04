"""
Phase 10E - Universal Selector & Permission-Based Filtering Test Suite
Verifies database-backed selector queries, search debouncing criteria,
role & vertical filters, downward assignment hierarchy enforcement,
and audience selection privileges.
"""

import secrets
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_session_token
from app.main import app
from app.models.event import Event, EventStatus, EventType
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User


@pytest.fixture
def selector_env(db_session: Session):
    """Sets up a comprehensive environment with users across roles, verticals, and events."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org", code="PARADOX")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    # Two distinct Verticals
    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket Operations {uid}",
        description="Cricket Vertical Division",
        status=VerticalStatus.ACTIVE,
    )
    v_football = Vertical(
        organization_id=org.id,
        name=f"Football Operations {uid}",
        description="Football Vertical Division",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_cricket, v_football])
    db_session.flush()

    # Canonical Roles
    r_admin = db_session.query(Role).filter_by(name="ADMIN").first()
    r_sports_core = db_session.query(Role).filter_by(name="SPORTS_CORE").first()
    r_deputy_core = db_session.query(Role).filter_by(name="DEPUTY_CORE").first()
    r_super_coord = db_session.query(Role).filter_by(name="SUPER_COORDINATOR").first()
    r_coord = db_session.query(Role).filter_by(name="COORDINATOR").first()
    r_vol = db_session.query(Role).filter_by(name="VOLUNTEER").first()
    r_event_team = db_session.query(Role).filter_by(name="EVENT_TEAM").first()

    # Users
    u_admin = User(
        username=f"admin_sel_{uid}",
        email=f"admin_sel_{uid}@test.oms",
        full_name=f"Alice Admin {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_sports_core = User(
        username=f"score_sel_{uid}",
        email=f"score_sel_{uid}@test.oms",
        full_name=f"Bob SportsCore {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_super_cricket = User(
        username=f"super_cric_{uid}",
        email=f"super_cric_{uid}@test.oms",
        full_name=f"Charlie SuperCoord {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_cricket = User(
        username=f"coord_cric_{uid}",
        email=f"coord_cric_{uid}@test.oms",
        full_name=f"Dan CricketCoord {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol_cricket = User(
        username=f"vol_cric_{uid}",
        email=f"vol_cric_{uid}@test.oms",
        full_name=f"Eve CricketVol {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_football = User(
        username=f"coord_foot_{uid}",
        email=f"coord_foot_{uid}@test.oms",
        full_name=f"Frank FootballCoord {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol_football = User(
        username=f"vol_foot_{uid}",
        email=f"vol_foot_{uid}@test.oms",
        full_name=f"Grace FootballVol {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_event_team = User(
        username=f"eteam_sel_{uid}",
        email=f"eteam_sel_{uid}@test.oms",
        full_name=f"Hank EventTeam {uid}",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )

    all_users = [
        u_admin,
        u_sports_core,
        u_super_cricket,
        u_coord_cricket,
        u_vol_cricket,
        u_coord_football,
        u_vol_football,
        u_event_team,
    ]
    db_session.add_all(all_users)
    db_session.flush()

    # Role mappings
    db_session.add_all([
        UserRole(user_id=u_admin.id, role_id=r_admin.id),
        UserRole(user_id=u_sports_core.id, role_id=r_sports_core.id),
        UserRole(user_id=u_super_cricket.id, role_id=r_super_coord.id),
        UserRole(user_id=u_coord_cricket.id, role_id=r_coord.id),
        UserRole(user_id=u_vol_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_coord_football.id, role_id=r_coord.id),
        UserRole(user_id=u_vol_football.id, role_id=r_vol.id),
        UserRole(user_id=u_event_team.id, role_id=r_event_team.id),
    ])

    # Vertical mappings
    db_session.add_all([
        UserVertical(user_id=u_super_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_coord_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_vol_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_coord_football.id, vertical_id=v_football.id, is_primary=True),
        UserVertical(user_id=u_vol_football.id, vertical_id=v_football.id, is_primary=True),
    ])

    db_session.commit()

    def make_auth_headers(user: User):
        raw_token = secrets.token_hex(32)
        sess = UserSession(
            user_id=user.id,
            session_token_hash=hash_session_token(raw_token),
            expires_at=datetime(2035, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(sess)
        db_session.commit()
        return {"Authorization": f"Bearer {raw_token}"}

    return {
        "v_cricket": v_cricket,
        "v_football": v_football,
        "u_admin": u_admin,
        "u_sports_core": u_sports_core,
        "u_super_cricket": u_super_cricket,
        "u_coord_cricket": u_coord_cricket,
        "u_vol_cricket": u_vol_cricket,
        "u_coord_football": u_coord_football,
        "u_vol_football": u_vol_football,
        "u_event_team": u_event_team,
        "headers": {u.username: make_auth_headers(u) for u in all_users},
    }


def test_selector_search_by_username_fullname_and_email(selector_env):
    """Verifies that search matches on username, full name, or email across active members."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]

        # 1. Search by username
        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=USER&search={selector_env['u_coord_cricket'].username}",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(item["id"] == str(selector_env["u_coord_cricket"].id) for item in data["items"])

        # 2. Search by full name (case-insensitive substring)
        res = client.get(
            "/api/v1/organization/selector-options?selection_type=USER&search=CricketCoord",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(item["id"] == str(selector_env["u_coord_cricket"].id) for item in data["items"])

        # 3. Search by email
        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=USER&search={selector_env['u_coord_football'].email}",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(item["id"] == str(selector_env["u_coord_football"].id) for item in data["items"])


def test_selector_filter_by_role(selector_env):
    """Verifies role filtering limits output strictly to users with the requested canonical role."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=USER&role_filter=VOLUNTEER",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["badge"] == "VOLUNTEER"
            assert "VOLUNTEER" in item["metadata"]["roles"]


def test_selector_filter_by_vertical(selector_env):
    """Verifies vertical filtering limits output strictly to members assigned to that vertical."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        vid = selector_env["v_cricket"].id

        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=USER&vertical_id={vid}",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        # Should include cricket super, coord, and vol, but NOT football members
        returned_ids = {item["id"] for item in data["items"]}
        assert str(selector_env["u_coord_cricket"].id) in returned_ids
        assert str(selector_env["u_vol_cricket"].id) in returned_ids
        assert str(selector_env["u_coord_football"].id) not in returned_ids
        assert str(selector_env["u_vol_football"].id) not in returned_ids


def test_selector_combined_role_and_vertical(selector_env):
    """Verifies combined filtering (e.g. COORDINATOR + Cricket Vertical)."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        vid = selector_env["v_cricket"].id

        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=USER&role_filter=COORDINATOR&vertical_id={vid}",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        returned_ids = [item["id"] for item in data["items"]]
        assert str(selector_env["u_coord_cricket"].id) in returned_ids
        assert str(selector_env["u_vol_cricket"].id) not in returned_ids
        assert str(selector_env["u_coord_football"].id) not in returned_ids


def test_selector_vertical_mode(selector_env):
    """Verifies selection_type=VERTICAL returns valid vertical divisions with search and badges."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]

        # 1. Broad query
        res = client.get(
            "/api/v1/organization/selector-options?selection_type=VERTICAL",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["selection_type"] == "VERTICAL"
        assert data["total"] >= 2
        for it in data["items"]:
            assert it["type"] == "VERTICAL"
            assert "badge" in it

        # 2. Search by exact created vertical name
        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=VERTICAL&search={selector_env['v_cricket'].name}",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(item["id"] == str(selector_env["v_cricket"].id) for item in data["items"])


def test_selector_role_mode(selector_env):
    """Verifies selection_type=ROLE returns canonical role options."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=ROLE",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["selection_type"] == "ROLE"
        role_ids = [item["id"] for item in data["items"]]
        assert "COORDINATOR" in role_ids
        assert "VOLUNTEER" in role_ids
        assert "SPORTS_CORE" in role_ids


def test_selector_event_team_mode(selector_env):
    """Verifies selection_type=EVENT_TEAM returns only designated Event Team accounts."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=EVENT_TEAM",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["selection_type"] == "EVENT_TEAM"
        for item in data["items"]:
            assert item["type"] == "EVENT_TEAM"
            assert item["badge"] == "EVENT_TEAM"
        team_ids = [item["id"] for item in data["items"]]
        assert str(selector_env["u_event_team"].id) in team_ids
        assert str(selector_env["u_coord_cricket"].id) not in team_ids


def test_assignment_hierarchy_coordinator_only_receives_volunteers_in_own_vertical(selector_env):
    """
    CRITICAL AUTHORIZATION RULE:
    When usage='assignment', a Coordinator (Level 2) can only assign downward (Level 1 Volunteer)
    and strictly within their assigned vertical division.
    They cannot see peers (Coordinators), superiors (Super Coord, Sports Core), or other verticals.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_coord_cricket"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=USER&usage=assignment",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        returned_ids = {item["id"] for item in data["items"]}

        # 1. Must include Volunteer in Cricket
        assert str(selector_env["u_vol_cricket"].id) in returned_ids

        # 2. Must NOT include Volunteer in Football (Cross-vertical isolation)
        assert str(selector_env["u_vol_football"].id) not in returned_ids

        # 3. Must NOT include self or fellow Coordinators (Equal-level authority violation)
        assert str(selector_env["u_coord_cricket"].id) not in returned_ids
        assert str(selector_env["u_coord_football"].id) not in returned_ids

        # 4. Must NOT include Super Coordinator or Sports Core (Upward hierarchy violation)
        assert str(selector_env["u_super_cricket"].id) not in returned_ids
        assert str(selector_env["u_sports_core"].id) not in returned_ids

        # 5. Must NOT include Admin
        assert str(selector_env["u_admin"].id) not in returned_ids


def test_assignment_hierarchy_super_coordinator_can_assign_to_coordinator_and_volunteer(selector_env):
    """
    Super Coordinator (Level 3) in Cricket can assign downward to both Coordinator (Level 2)
    and Volunteer (Level 1) in Cricket, but not across verticals or upward to Sports Core.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_super_cricket"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=USER&usage=assignment",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        returned_ids = {item["id"] for item in data["items"]}

        # Allowed downward targets in Cricket
        assert str(selector_env["u_coord_cricket"].id) in returned_ids
        assert str(selector_env["u_vol_cricket"].id) in returned_ids

        # Blocked: Football vertical members
        assert str(selector_env["u_coord_football"].id) not in returned_ids
        assert str(selector_env["u_vol_football"].id) not in returned_ids

        # Blocked: Upward Sports Core
        assert str(selector_env["u_sports_core"].id) not in returned_ids


def test_assignment_hierarchy_volunteer_cannot_assign_work(selector_env):
    """Volunteer (Level 1) has no downward hierarchy and cannot assign work to others."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_vol_cricket"].username]

        res = client.get(
            "/api/v1/organization/selector-options?selection_type=USER&usage=assignment",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        # Volunteer cannot assign to anyone
        assert data["total"] == 0
        assert len(data["items"]) == 0


def test_selector_search_by_id(selector_env):
    """Test searching user by ID."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_admin"].username]
        u = selector_env["u_coord_cricket"]
        res = client.get(f"/api/v1/users/selector?search={u.id}", headers=hdrs)
        assert res.status_code == 200
        data = res.json()
        assert any(item["id"] == str(u.id) for item in data["items"])


def test_selector_search_with_empty_string(selector_env):
    """Test searching with empty string returns default scoped list."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_admin"].username]
        res = client.get("/api/v1/users/selector?search=", headers=hdrs)
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) > 0


def test_users_selector_route_alias(selector_env):
    """Verify /api/v1/users/selector returns valid structure with pagination."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_admin"].username]
        res = client.get("/api/v1/users/selector?page=1&limit=5", headers=hdrs)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "groups" in data
        assert "users" in data


def test_selector_groups_with_realtime_member_counts(selector_env):
    """Verify groups return accurate real-time member counts."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_admin"].username]
        v_name = selector_env["v_cricket"].name
        res = client.get(f"/api/v1/organization/selector-options?selection_type=VERTICAL&search={v_name}", headers=hdrs)
        assert res.status_code == 200
        data = res.json()
        cricket_item = next((it for it in data["items"] if it["id"] == str(selector_env["v_cricket"].id)), None)
        assert cricket_item is not None
        assert cricket_item["member_count"] is not None
        assert cricket_item["member_count"] >= 3  # super, coord, vol


def test_selector_role_vertical_combinations(selector_env):
    """Verify ROLE_VERTICAL combination returns pair item with accurate member count."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_admin"].username]
        v_id = str(selector_env["v_cricket"].id)
        res = client.get(
            f"/api/v1/organization/selector-options?selection_type=ROLE_VERTICAL&vertical_id={v_id}&role_filter=COORDINATOR",
            headers=hdrs,
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) >= 1
        item = data["items"][0]
        assert item["type"] == "ROLE_VERTICAL"
        assert item["member_count"] is not None
        assert item["member_count"] >= 1
        assert "COORDINATOR" in item["id"]


def test_selector_all_users_group_count(selector_env):
    """Verify ALL_USERS returns total active organization members count."""
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        res = client.get("/api/v1/organization/selector-options?selection_type=ALL_USERS", headers=hdrs)
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["member_count"] is not None
        assert data["items"][0]["member_count"] >= 5


def test_event_poc_internal_user_id_handling(selector_env, db_session: Session):
    """
    Verify Event creation strictly associates internal platform users as
    event_head_id, primary_poc_id, and EventMember POCs.
    """
    from app.services.event_service import EventService
    from app.schemas.event import EventCreate
    from app.models.event import EventMember, EventMemberRole
    from datetime import date

    svc = EventService(db_session)
    admin_u = selector_env["u_admin"]
    head_u = selector_env["u_coord_cricket"]
    poc_u = selector_env["u_vol_cricket"]
    extra_poc_u = selector_env["u_coord_football"]

    data = EventCreate(
        name="Phase 10E Test Cup",
        vertical_id=selector_env["v_cricket"].id,
        event_type=EventType.TOURNAMENT,
        planned_date=date(2026, 10, 15),
        event_head_user_id=head_u.id,
        primary_poc_user_id=poc_u.id,
        additional_poc_user_ids=[extra_poc_u.id],
        additional_pocs=[
            {"name": "Vendor Sponsor", "phone": "555-1234", "email": "vendor@test.oms", "designation": "Supplier"}
        ],
    )

    ev = svc.create_event(data, actor_id=admin_u.id)
    assert ev.event_head_id == head_u.id
    assert ev.primary_poc_id == poc_u.id

    # Verify additional POC member record
    extra_member = db_session.query(EventMember).filter_by(
        event_id=ev.id, user_id=extra_poc_u.id, role_in_event=EventMemberRole.POC
    ).first()
    assert extra_member is not None

    # Verify external POC stored in resource_links
    assert ev.resource_links["additional_pocs"][0]["name"] == "Vendor Sponsor"


def test_meeting_create_with_group_audience(selector_env, db_session: Session):
    """
    Verify Meeting creation accepts group audience (target_vertical_ids, target_roles)
    and resolves active users directly without bloating frontend payload.
    """
    from app.services.meeting_service import MeetingService
    from app.schemas.meeting import MeetingCreate
    from app.models.meeting import MeetingParticipant
    from datetime import date

    svc = MeetingService(db_session)
    admin_u = selector_env["u_admin"]
    v_cricket = selector_env["v_cricket"]

    meeting_data = MeetingCreate(
        title="Phase 10E Operations Alignment",
        meeting_date=date(2026, 10, 20),
        vertical_id=v_cricket.id,
        target_vertical_ids=[v_cricket.id],
    )

    meeting = svc.create_meeting(meeting_data, organizer_id=admin_u.id)
    assert meeting.id is not None

    # Check participants invited
    participants = db_session.query(MeetingParticipant).filter_by(meeting_id=meeting.id).all()
    participant_user_ids = {p.user_id for p in participants}

    # Cricket members should be resolved and invited
    assert selector_env["u_coord_cricket"].id in participant_user_ids
    assert selector_env["u_vol_cricket"].id in participant_user_ids


def test_audience_selection_privileges(selector_env):
    """
    ALL_USERS mode is permitted for Executive/Admin broadcast,
    but prohibited for standard volunteers.
    """
    with TestClient(app) as client:
        # 1. Sports Core (Executive) -> Allowed
        hdrs_score = selector_env["headers"][selector_env["u_sports_core"].username]
        res = client.get(
            "/api/v1/organization/selector-options?selection_type=ALL_USERS",
            headers=hdrs_score,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "ALL"

        # 2. Volunteer -> Disallowed (returns empty options)
        hdrs_vol = selector_env["headers"][selector_env["u_vol_cricket"].username]
        res = client.get(
            "/api/v1/organization/selector-options?selection_type=ALL_USERS",
            headers=hdrs_vol,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0


def test_contract_validation_for_forms():
    """
    Verify Pydantic schemas enforce type safety and reject invalid inputs.
    """
    from pydantic import ValidationError
    from app.schemas.event import EventCreate
    from app.schemas.meeting import MeetingCreate
    from datetime import date
    import uuid

    # EventCreate requires valid name and planned_date
    with pytest.raises(ValidationError):
        EventCreate(vertical_id=uuid.uuid4(), name="", event_type="TOURNAMENT", planned_date=date.today())

    # MeetingCreate requires title
    with pytest.raises(ValidationError):
        MeetingCreate(title="", meeting_date=date.today())


# ==============================================================================
# SECTION 27: REQUIRED ACCEPTANCE TEST SUITE (Tests 1 through 10)
# ==============================================================================

def test_acceptance_1_vertical_selection(selector_env):
    """
    Test 1: Select Vertical -> Cricket
    Expected: All eligible active users belonging to the Cricket vertical.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        payload = {
            "all_users": False,
            "vertical_ids": [str(selector_env["v_cricket"].id)],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        resolved_ids = set(data["user_ids"])
        assert str(selector_env["u_super_cricket"].id) in resolved_ids
        assert str(selector_env["u_coord_cricket"].id) in resolved_ids
        assert str(selector_env["u_vol_cricket"].id) in resolved_ids
        # Football-only users must not be in the selection
        assert str(selector_env["u_coord_football"].id) not in resolved_ids
        assert str(selector_env["u_vol_football"].id) not in resolved_ids


def test_acceptance_2_role_selection(selector_env):
    """
    Test 2: Select Role -> Volunteer
    Expected: All eligible active users whose role is VOLUNTEER.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        payload = {
            "all_users": False,
            "role_ids": ["VOLUNTEER"],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        resolved_ids = set(data["user_ids"])
        assert str(selector_env["u_vol_cricket"].id) in resolved_ids
        assert str(selector_env["u_vol_football"].id) in resolved_ids
        # Non-volunteers must not be present
        assert str(selector_env["u_coord_cricket"].id) not in resolved_ids
        assert str(selector_env["u_coord_football"].id) not in resolved_ids


def test_acceptance_3_vertical_plus_role_combination(selector_env):
    """
    Test 3: Select Vertical -> Cricket + Role -> Volunteer
    Expected: All active VOLUNTEER users belonging to the Cricket vertical ((Cricket) AND (Volunteer)).
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        payload = {
            "all_users": False,
            "vertical_ids": [str(selector_env["v_cricket"].id)],
            "role_ids": ["VOLUNTEER"],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        resolved_ids = set(data["user_ids"])
        # Only Cricket Volunteer
        assert str(selector_env["u_vol_cricket"].id) in resolved_ids
        # Football volunteer excluded
        assert str(selector_env["u_vol_football"].id) not in resolved_ids
        # Cricket coordinator excluded
        assert str(selector_env["u_coord_cricket"].id) not in resolved_ids


def test_acceptance_4_multiple_verticals_or_semantics(selector_env):
    """
    Test 4: Select Cricket + Football
    Expected: All eligible users from both verticals (Cricket OR Football).
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        payload = {
            "all_users": False,
            "vertical_ids": [str(selector_env["v_cricket"].id), str(selector_env["v_football"].id)],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        resolved_ids = set(data["user_ids"])
        assert str(selector_env["u_coord_cricket"].id) in resolved_ids
        assert str(selector_env["u_vol_cricket"].id) in resolved_ids
        assert str(selector_env["u_coord_football"].id) in resolved_ids
        assert str(selector_env["u_vol_football"].id) in resolved_ids


def test_acceptance_5_multiple_roles_or_semantics(selector_env):
    """
    Test 5: Select Volunteer + Coordinator
    Expected: All eligible active Volunteers + Coordinators (Volunteer OR Coordinator).
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        payload = {
            "all_users": False,
            "role_ids": ["VOLUNTEER", "COORDINATOR"],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        resolved_ids = set(data["user_ids"])
        assert str(selector_env["u_vol_cricket"].id) in resolved_ids
        assert str(selector_env["u_vol_football"].id) in resolved_ids
        assert str(selector_env["u_coord_cricket"].id) in resolved_ids
        assert str(selector_env["u_coord_football"].id) in resolved_ids
        # Super coordinator not in [VOLUNTEER, COORDINATOR]
        assert str(selector_env["u_super_cricket"].id) not in resolved_ids


def test_acceptance_6_search_by_username_and_fullname(selector_env):
    """
    Test 6: Search username and full name
    Expected: Returns matching users from universal search field.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        # Search by username prefix
        res_user = client.get(
            f"/api/v1/users/selector?selection_type=USER&search={selector_env['u_vol_cricket'].username}",
            headers=hdrs,
        )
        assert res_user.status_code == 200
        items_user = res_user.json()["items"]
        assert any(it["id"] == str(selector_env["u_vol_cricket"].id) for it in items_user)

        # Search by full name keyword
        res_name = client.get(
            "/api/v1/users/selector?selection_type=USER&search=Eve CricketVol",
            headers=hdrs,
        )
        assert res_name.status_code == 200
        items_name = res_name.json()["items"]
        assert any(it["id"] == str(selector_env["u_vol_cricket"].id) for it in items_name)


def test_acceptance_7_search_by_email(selector_env):
    """
    Test 7: Search email
    Expected: Returns matching users from universal search field when searching email.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        target_email = selector_env["u_vol_football"].email
        res = client.get(
            f"/api/v1/users/selector?selection_type=USER&search={target_email}",
            headers=hdrs,
        )
        assert res.status_code == 200
        items = res.json()["items"]
        assert any(it["id"] == str(selector_env["u_vol_football"].id) for it in items)


def test_acceptance_8_combination_with_individual_user_deduplication(selector_env):
    """
    Test 8: Select Cricket + Rahul/Eve (individual) + Volunteer
    Expected: Deduplicated final user ID set. A user matching vertical, role, and
    individual selection occurs exactly once in the final resolved list.
    """
    with TestClient(app) as client:
        hdrs = selector_env["headers"][selector_env["u_sports_core"].username]
        u_vol_cric = selector_env["u_vol_cricket"]
        u_coord_foot = selector_env["u_coord_football"]

        payload = {
            "all_users": False,
            "vertical_ids": [str(selector_env["v_cricket"].id)],
            "role_ids": ["VOLUNTEER"],
            # u_vol_cric is selected both through (Cricket AND Volunteer) AND as an individual user
            "user_ids": [str(u_vol_cric.id), str(u_coord_foot.id)],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs)
        assert res.status_code == 200, res.text
        data = res.json()

        user_ids = data["user_ids"]
        # Verify deduplication: no ID appears twice
        assert len(user_ids) == len(set(user_ids))
        # Total count matches set length
        assert data["total_count"] == len(user_ids)
        # Both u_vol_cric and u_coord_foot are present
        assert str(u_vol_cric.id) in user_ids
        assert str(u_coord_foot.id) in user_ids


def test_acceptance_9_all_users_scope_privileges(selector_env):
    """
    Test 9: Select All Users
    Expected: All users within caller's authorized targeting scope.
    Executive succeeds; regular volunteer receives 403 Forbidden.
    """
    with TestClient(app) as client:
        # 1. Executive Core -> Authorized
        hdrs_score = selector_env["headers"][selector_env["u_sports_core"].username]
        res_exec = client.post(
            "/api/v1/users/resolve-audience",
            json={"all_users": True},
            headers=hdrs_score,
        )
        assert res_exec.status_code == 200
        assert res_exec.json()["total_count"] >= 5

        # 2. Volunteer -> Unauthorized (403 Forbidden)
        hdrs_vol = selector_env["headers"][selector_env["u_vol_cricket"].username]
        res_vol = client.post(
            "/api/v1/users/resolve-audience",
            json={"all_users": True},
            headers=hdrs_vol,
        )
        assert res_vol.status_code == 403
        err_msg = res_vol.json().get("error", {}).get("message") or res_vol.text
        assert "not authorized to target the entire organization" in err_msg


def test_acceptance_10_direct_api_unauthorized_user_uuid_injection_blocked(selector_env):
    """
    Test 10: Attempt direct API submission with an unauthorized user's UUID.
    Expected: 403 Forbidden. A coordinator in Cricket attempting to target a
    user in Football directly via API payload injection is rejected.
    """
    with TestClient(app) as client:
        # Dan CricketCoord tries to directly inject Frank FootballCoord's UUID
        hdrs_coord = selector_env["headers"][selector_env["u_coord_cricket"].username]
        payload = {
            "all_users": False,
            "user_ids": [str(selector_env["u_coord_football"].id)],
        }
        res = client.post("/api/v1/users/resolve-audience", json=payload, headers=hdrs_coord)
        assert res.status_code == 403
        err_msg = res.json().get("error", {}).get("message") or res.text
        assert "outside your authorized operational scope" in err_msg




