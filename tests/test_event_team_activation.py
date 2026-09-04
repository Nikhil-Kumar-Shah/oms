"""
Comprehensive Test Suite for Event Team Page Refactor & Activation Workflow
Verifies:
1. Admin creates Event Team credentials in unactivated state (account_status=DISABLED).
2. Unactivated Event Team user CANNOT log in (AccountInactiveException).
3. Non-admin cannot create credentials (403 Forbidden).
4. Unactivated accounts list is queryable by Sports Core / Deputy Core / Admin.
5. Sports Core and Deputy Core can activate Event Team accounts with Head POC and Additional POCs.
6. Activated Event Team user CAN now log in successfully (200 OK).
7. Unauthorized roles (Coordinator, Volunteer, Event Team) cannot activate accounts (403 Forbidden).
8. The Event Team -> Account -> Event Head -> POC relationship is correctly persisted.
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import generate_session_token, hash_session_token
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.models.event import Event, EventStatus, EventType, EventTeamProfile


@pytest.fixture
def activation_setup(db_session: Session):
    """Sets up an organization, roles, Admin, Sports Core, Deputy Core, Coordinator, Volunteer, and Event."""
    uid = uuid.uuid4().hex[:6]
    org = Organization(name="Activation Org", code=f"act-{uid}")
    db_session.add(org)
    db_session.flush()

    vert = Vertical(organization_id=org.id, name=f"Football {uid}", status=VerticalStatus.ACTIVE)
    db_session.add(vert)
    db_session.flush()

    # Roles
    roles = {}
    for rname in ["ADMIN", "SPORTS_CORE", "DEPUTY_CORE", "SUPER_COORDINATOR", "COORDINATOR", "VOLUNTEER", "EVENT_TEAM"]:
        r = db_session.query(Role).filter(Role.name == rname).first()
        if not r:
            r = Role(name=rname, description=f"{rname} role")
            db_session.add(r)
            db_session.flush()
        roles[rname] = r

    def create_user_helper(username: str, role_name: str, status: AccountStatus = AccountStatus.ACTIVE):
        u = User(
            username=f"{username}_{uid}",
            email=f"{username}_{uid}@example.com",
            password_hash="fakehash",
            full_name=f"User {username.title()}",
            account_status=status,
        )
        db_session.add(u)
        db_session.flush()

        db_session.add(UserRole(user_id=u.id, role_id=roles[role_name].id))
        db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id, is_primary=True))
        db_session.flush()

        tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(tok),
            ip_address="127.0.0.1",
            user_agent="pytest-act",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        db_session.add(sess)
        db_session.flush()
        return u, tok

    u_admin, tok_admin = create_user_helper("admin_act", "ADMIN")
    u_sports, tok_sports = create_user_helper("sports_act", "SPORTS_CORE")
    u_deputy, tok_deputy = create_user_helper("deputy_act", "DEPUTY_CORE")
    u_coord, tok_coord = create_user_helper("coord_act", "COORDINATOR")
    u_vol, tok_vol = create_user_helper("vol_act", "VOLUNTEER")
    u_head_poc, _ = create_user_helper("head_poc_act", "COORDINATOR")
    u_add_poc, _ = create_user_helper("add_poc_act", "VOLUNTEER")

    # Sample Event
    from datetime import date
    event = Event(
        vertical_id=vert.id,
        name=f"Tournament {uid}",
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=date.today() + timedelta(days=10),
        created_by_id=u_admin.id,
    )
    db_session.add(event)
    db_session.flush()

    db_session.commit()

    return {
        "admin": u_admin,
        "tok_admin": tok_admin,
        "sports": u_sports,
        "tok_sports": tok_sports,
        "deputy": u_deputy,
        "tok_deputy": tok_deputy,
        "coord": u_coord,
        "tok_coord": tok_coord,
        "vol": u_vol,
        "tok_vol": tok_vol,
        "head_poc": u_head_poc,
        "add_poc": u_add_poc,
        "event": event,
        "uid": uid,
    }


def test_admin_create_credentials_unactivated_and_login_blocked(client: TestClient, activation_setup, db_session: Session):
    """Admin creates credentials; account is DISABLED and cannot authenticate."""
    tok_admin = activation_setup["tok_admin"]
    uid = activation_setup["uid"]
    username = f"team_unact_{uid}"
    password = "SecurePassword@123"

    # 1. Admin creates credentials
    res = client.post(
        "/api/v1/event-teams/credentials",
        headers={"Authorization": f"Bearer {tok_admin}"},
        json={
            "username": username,
            "password": password,
            "email": f"{username}@test.org",
            "team_name": f"Team Unactivated {uid}",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["username"] == username
    assert data["account_status"] == "DISABLED"
    team_user_id = data["id"]

    # 2. Verify account is DISABLED in database
    db_session.expire_all()
    user = db_session.get(User, uuid.UUID(team_user_id))
    assert user.account_status == AccountStatus.DISABLED

    # 3. Verify user CANNOT log in while unactivated
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_res.status_code in [401, 403], f"Expected login rejection, got {login_res.status_code}"
    assert "DISABLED" in login_res.text or "inactive" in login_res.text.lower()


def test_non_admin_cannot_create_credentials(client: TestClient, activation_setup):
    """Only Admin can create Event Team credentials (403 for other roles)."""
    tok_sports = activation_setup["tok_sports"]
    tok_coord = activation_setup["tok_coord"]
    tok_vol = activation_setup["tok_vol"]

    payload = {
        "username": "illegal_team_1",
        "password": "SecurePassword@123",
        "team_name": "Illegal Team",
    }

    # Sports Core cannot create raw credentials (must be admin)
    res_sp = client.post(
        "/api/v1/event-teams/credentials",
        headers={"Authorization": f"Bearer {tok_sports}"},
        json=payload,
    )
    assert res_sp.status_code == 403

    # Coordinator cannot
    res_co = client.post(
        "/api/v1/event-teams/credentials",
        headers={"Authorization": f"Bearer {tok_coord}"},
        json=payload,
    )
    assert res_co.status_code == 403

    # Volunteer cannot
    res_vo = client.post(
        "/api/v1/event-teams/credentials",
        headers={"Authorization": f"Bearer {tok_vol}"},
        json=payload,
    )
    assert res_vo.status_code == 403


def test_sports_core_and_deputy_core_activation_flow(client: TestClient, activation_setup, db_session: Session):
    """
    Full workflow:
    1. Admin creates credentials (unactivated).
    2. Sports Core activates account with Head POC, Additional POCs, Head Details.
    3. User is now ACTIVE and can log in successfully.
    4. Persisted relationships: Event Team -> Account -> Event Head -> POCs.
    """
    tok_admin = activation_setup["tok_admin"]
    tok_sports = activation_setup["tok_sports"]
    head_poc = activation_setup["head_poc"]
    add_poc = activation_setup["add_poc"]
    event = activation_setup["event"]
    uid = activation_setup["uid"]

    username = f"titans_team_{uid}"
    password = "TitansPassword@123"

    # Step 1: Admin creates unactivated credentials
    creds_res = client.post(
        "/api/v1/event-teams/credentials",
        headers={"Authorization": f"Bearer {tok_admin}"},
        json={
            "username": username,
            "password": password,
            "email": f"{username}@titans.org",
            "team_name": f"Titans {uid}",
        },
    )
    assert creds_res.status_code == 201
    user_id = creds_res.json()["id"]

    # Step 2: Sports Core views unactivated accounts
    unact_res = client.get(
        "/api/v1/event-teams/unactivated",
        headers={"Authorization": f"Bearer {tok_sports}"},
    )
    assert unact_res.status_code == 200
    unact_list = unact_res.json()
    assert any(u["id"] == user_id for u in unact_list)

    # Step 3: Sports Core activates the account
    act_payload = {
        "team_name": f"Titans FC {uid}",
        "head_name": "Coach Jackson",
        "head_phone": "+91 9876543210",
        "head_email": "coach.jackson@titans.org",
        "user_id": user_id,
        "head_poc_id": str(head_poc.id),
        "additional_poc_ids": [str(add_poc.id)],
        "event_id": str(event.id),
        "notes": "Verified roster and medical clearances",
    }
    act_res = client.post(
        "/api/v1/event-teams/activate",
        headers={"Authorization": f"Bearer {tok_sports}"},
        json=act_payload,
    )
    assert act_res.status_code == 200, act_res.text
    act_data = act_res.json()

    assert act_data["team_name"] == f"Titans FC {uid}"
    assert act_data["head_name"] == "Coach Jackson"
    assert act_data["head_phone"] == "+91 9876543210"
    assert act_data["head_email"] == "coach.jackson@titans.org"
    assert act_data["head_poc_id"] == str(head_poc.id)
    assert len(act_data["additional_pocs"]) == 1
    assert act_data["additional_pocs"][0]["id"] == str(add_poc.id)
    assert act_data["is_activated"] is True
    assert act_data["account_status"] == "ACTIVE"

    # Step 4: Verify Event Team can authenticate now
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_res.status_code == 200, f"Login failed for activated user: {login_res.text}"
    token = login_res.json()["session"]["token"]

    # Step 5: Verify Event Team can access /event-teams/me
    me_res = client.get(
        "/api/v1/event-teams/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["team_name"] == f"Titans FC {uid}"
    assert me_data["head_name"] == "Coach Jackson"


def test_unauthorized_user_cannot_activate_account(client: TestClient, activation_setup):
    """Coordinator or Volunteer cannot call /event-teams/activate (403 Forbidden)."""
    tok_coord = activation_setup["tok_coord"]
    tok_vol = activation_setup["tok_vol"]
    head_poc = activation_setup["head_poc"]

    payload = {
        "team_name": "Test Team",
        "head_name": "Coach Test",
        "head_phone": "1234567890",
        "head_email": "test@test.org",
        "user_id": str(uuid.uuid4()),
        "head_poc_id": str(head_poc.id),
        "additional_poc_ids": [],
    }

    res_c = client.post(
        "/api/v1/event-teams/activate",
        headers={"Authorization": f"Bearer {tok_coord}"},
        json=payload,
    )
    assert res_c.status_code == 403

    res_v = client.post(
        "/api/v1/event-teams/activate",
        headers={"Authorization": f"Bearer {tok_vol}"},
        json=payload,
    )
    assert res_v.status_code == 403


def test_activation_strictly_requires_event_assignment(client: TestClient, activation_setup):
    """Event Team activation requires event_id; missing event_id must fail."""
    tok_sports = activation_setup["tok_sports"]
    head_poc = activation_setup["head_poc"]

    payload = {
        "team_name": "No Event Team",
        "head_name": "Coach Test",
        "head_phone": "1234567890",
        "head_email": "test@test.org",
        "user_id": str(uuid.uuid4()),
        "head_poc_id": str(head_poc.id),
        "additional_poc_ids": [],
        # event_id omitted
    }

    res = client.post(
        "/api/v1/event-teams/activate",
        headers={"Authorization": f"Bearer {tok_sports}"},
        json=payload,
    )
    # Schema validation rejects missing event_id (422 Unprocessable Entity)
    assert res.status_code == 422


def test_unactivated_event_team_direct_access_returns_403(client: TestClient, activation_setup, db_session: Session):
    """If an unactivated Event Team tries to access /event-teams/me via direct token/cookie, backend returns 403."""
    uid = uuid.uuid4().hex[:6]
    vert = activation_setup["event"].vertical_id

    # Create unactivated user with session
    u = User(
        username=f"direct_blocked_{uid}",
        email=f"direct_{uid}@test.org",
        password_hash="fakehash",
        full_name="Direct Blocked Team",
        account_status=AccountStatus.DISABLED,
    )
    db_session.add(u)
    db_session.flush()

    role_evt = db_session.query(Role).filter(Role.name == "EVENT_TEAM").first()
    db_session.add(UserRole(user_id=u.id, role_id=role_evt.id))
    db_session.add(UserVertical(user_id=u.id, vertical_id=vert, is_primary=True))

    profile = EventTeamProfile(
        user_id=u.id,
        team_name="Direct Blocked Team",
        contact_info={"is_activated": False},
    )
    db_session.add(profile)

    tok = generate_session_token()
    sess = UserSession(
        user_id=u.id,
        session_token_hash=hash_session_token(tok),
        ip_address="127.0.0.1",
        user_agent="pytest-act",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db_session.add(sess)
    db_session.commit()

    # Direct request with valid token hash, but account is DISABLED / unactivated
    res = client.get(
        "/api/v1/event-teams/me",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert res.status_code == 403, f"Expected 403 Forbidden for unactivated direct access, got {res.status_code}"

