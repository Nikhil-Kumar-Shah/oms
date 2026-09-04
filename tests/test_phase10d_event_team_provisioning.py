"""
Tests for Phase 10D: Event Team Account Provisioning & Profile Ownership
Paradox Sports OMS - Isolated Event Team Identity & Operational Boundary Governance
"""

import uuid
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.event import Event, EventStatus, EventType, EventTeamProfile
from app.models.organization import Vertical
from app.models.user import User, AccountStatus
from app.models.rbac import Role, UserRole
from app.services.event_team_service import EventTeamService
from app.schemas.event_team import EventTeamCreate, EventTeamUpdate


def _login_and_get_token(client: TestClient, username: str, password: str) -> dict:
    """Helper to authenticate and return auth headers."""
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_provision_event_team_without_event_id(
    client: TestClient, db_session: Session, admin_user: User
):
    """
    Verifies ADMIN can provision an EVENT_TEAM account with only required fields:
    Username *, Full Name *, Email Address *, Password *.
    No event_id, no head_name, no head_phone required.
    """
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]
    username = f"team_isolated_{suffix}"
    email = f"contact_{suffix}@squad.org"
    password = "SecurePassword@123"

    payload = {
        "username": username,
        "full_name": f"Strikers FC {suffix}",
        "email": email,
        "password": password,
    }

    resp = client.post("/api/v1/event-teams", json=payload, headers=headers)
    assert resp.status_code == 201, f"Failed to provision Event Team: {resp.text}"
    data = resp.json()

    # 1. Profile metadata assertions
    assert data["username"] == username
    assert data["team_name"] == f"Strikers FC {suffix}"
    assert data["event_id"] is None
    assert data["event_name"] is None

    # 2. Database verification in PostgreSQL
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    assert user.account_status == AccountStatus.ACTIVE
    assert user.email == email

    # Verify EVENT_TEAM role is assigned
    user_roles = db_session.scalars(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    ).all()
    assert "EVENT_TEAM" in user_roles

    # Verify profile exists in PostgreSQL without event association
    profile = db_session.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == user.id))
    assert profile is not None
    assert profile.event_id is None
    assert profile.team_name == f"Strikers FC {suffix}"

    # 3. Verify newly provisioned EVENT_TEAM can authenticate immediately
    login_resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login_resp.status_code == 200
    assert "session" in login_resp.json()


def test_admin_provision_event_team_with_optional_head_details(
    client: TestClient, db_session: Session, admin_user: User
):
    """Verifies ADMIN can provision an EVENT_TEAM account with optional head details."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]
    username = f"team_head_{suffix}"
    email = f"head_{suffix}@contingent.org"
    password = "SecurePassword@123"

    payload = {
        "username": username,
        "full_name": f"United Basketball {suffix}",
        "email": email,
        "password": password,
        "head_name": "Coach Marcus",
        "head_phone": "+1 555-0188",
    }

    resp = client.post("/api/v1/event-teams", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["head_name"] == "Coach Marcus"
    assert data["head_phone"] == "+1 555-0188"
    assert data["event_id"] is None


def test_subsequent_event_association_workflow(
    client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical
):
    """
    Verifies that an unassigned Event Team account can later be associated
    with an Event through the operational update workflow.
    """
    admin_headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]

    # 1. Provision unassigned Event Team account
    team_payload = {
        "username": f"team_unassigned_{suffix}",
        "full_name": f"Thunder Track Club {suffix}",
        "email": f"thunder_{suffix}@track.org",
        "password": "SecurePassword@123",
    }
    create_resp = client.post("/api/v1/event-teams", json=team_payload, headers=admin_headers)
    assert create_resp.status_code == 201
    team_data = create_resp.json()
    team_id = team_data["id"]
    assert team_data["event_id"] is None

    # 2. Create an Event in PLANNING status
    today = date.today()
    event = Event(
        name=f"National Track Championships {suffix}",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=today + timedelta(days=15),
        created_by_id=admin_user.id,
    )
    db_session.add(event)
    db_session.commit()

    # 3. Associate Event Team profile with the Event
    update_payload = {
        "event_id": str(event.id),
        "notes": "Assigned to Lane 4 Track Event.",
    }
    update_resp = client.put(f"/api/v1/event-teams/{team_id}", json=update_payload, headers=admin_headers)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()

    assert updated_data["event_id"] == str(event.id)
    assert updated_data["event_name"] == event.name
    assert updated_data["notes"] == "Assigned to Lane 4 Track Event."

    # 4. Verify in PostgreSQL
    db_session.expire_all()
    profile = db_session.get(EventTeamProfile, uuid.UUID(team_id))
    assert profile.event_id == event.id


def test_event_team_self_profile_update_and_boundary_isolation(
    client: TestClient, db_session: Session, admin_user: User
):
    """
    Verifies that an EVENT_TEAM account can maintain its own operational details
    via /event-teams/me, and cannot access internal administrative endpoints.
    """
    admin_headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]
    username = f"team_self_{suffix}"
    password = "SecurePassword@123"

    # 1. Provision account
    create_resp = client.post(
        "/api/v1/event-teams",
        json={
            "username": username,
            "full_name": f"Aero Badminton {suffix}",
            "email": f"aero_{suffix}@badminton.org",
            "password": password,
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201

    # 2. Login as EVENT_TEAM
    team_headers = _login_and_get_token(client, username, password)

    # 3. Get /event-teams/me
    me_resp = client.get("/api/v1/event-teams/me", headers=team_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == username

    # 4. Update /event-teams/me (self-service)
    put_resp = client.put(
        "/api/v1/event-teams/me",
        json={
            "head_name": "Captain Lin",
            "head_phone": "+1 555-9988",
            "members_summary": [
                {"name": "Lin", "role": "Captain", "contact": "+1 555-9988"},
                {"name": "Chen", "role": "Player"},
            ],
            "notes": "Arrival expected 2 hours prior to matches.",
        },
        headers=team_headers,
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["head_name"] == "Captain Lin"
    assert len(data["members_summary"]) == 2

    # 5. Boundary Isolation: EVENT_TEAM must be blocked from administrative routes
    admin_users_resp = client.get("/api/v1/admin/users", headers=team_headers)
    assert admin_users_resp.status_code in [401, 403]
