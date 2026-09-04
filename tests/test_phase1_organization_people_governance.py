"""
Phase 1: Organization + People + Role Governance Test Suite
Paradox Sports OMS - Authoritative Product Specification Verification

Verifies:
1. Canonical 7 Roles & Role Capability Matrix
2. Dynamic Database-Backed Organization & Vertical Lifecycle (Create, Edit, Disable, Archive)
3. Internal vs Event Team User Account Creation & Profile Separation
4. Event-Specific POC Group Management (Exactly 1 Head POC + POC Members + Vertical Scoping)
5. Event Team Strict Operational Isolation (Denial of internal audit, governance, users, other teams)
6. Scope Enforcement (USER_SCOPE, VERTICAL_SCOPE, EVENT_SCOPE, ORGANIZATION_SCOPE)
7. Permission Escalation & IDOR Defense
8. Fresh-Session PostgreSQL Persistence Truth
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.middleware import RateLimitingMiddleware
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventStatus,
    EventTeamProfile,
    EventType,
)
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import AccountStatus, User, UserAvailability, UserProfile
from app.schemas.event import POCGroupAssignRequest
from app.schemas.event_team import EventTeamCreate, EventTeamUpdate
from app.schemas.organization import VerticalCreate, VerticalUpdate
from app.schemas.user import UserCreate
from app.services.event_service import EventService
from app.services.event_team_service import EventTeamService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService
from app.services.user_service import UserService


def _login_and_get_token(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    RateLimitingMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Canonical 7 Roles & Capability Matrix Verification
# =============================================================================

def test_canonical_roles_exist_in_database(db_session: Session):
    """Verifies all 7 canonical roles defined in Product Specification exist."""
    expected_roles = [
        "ADMIN",
        "SPORTS_CORE",
        "DEPUTY_CORE",
        "SUPER_COORDINATOR",
        "COORDINATOR",
        "VOLUNTEER",
        "EVENT_TEAM",
    ]
    roles = db_session.scalars(select(Role)).all()
    role_names = {r.name for r in roles}

    for expected in expected_roles:
        assert expected in role_names, f"Canonical role '{expected}' missing from database"


def test_rbac_effective_permissions_across_hierarchy(db_session: Session):
    """Verifies server-authoritative effective permission calculation across the role hierarchy."""
    rbac = RbacService(db_session)
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
    role_vol = db_session.scalar(select(Role).where(Role.name == "VOLUNTEER"))

    admin_u = user_service.create_user(
        UserCreate(
            username=f"admin_cap_{suffix}",
            full_name="Admin Cap Test",
            password="SecurePassword123!",
            role_ids=[role_admin.id],
        )
    )
    vol_u = user_service.create_user(
        UserCreate(
            username=f"vol_cap_{suffix}",
            full_name="Vol Cap Test",
            password="SecurePassword123!",
            role_ids=[role_vol.id],
        )
    )
    db_session.commit()

    admin_perms = rbac.get_effective_permissions(admin_u.id)
    vol_perms = rbac.get_effective_permissions(vol_u.id)

    # Admin possesses all permissions
    assert "users.create" in admin_perms
    assert "verticals.create" in admin_perms
    assert "audit.read" in admin_perms

    # Volunteer does not possess administrative creation permissions
    assert "users.create" not in vol_perms
    assert "verticals.create" not in vol_perms
    assert "audit.read" not in vol_perms


# =============================================================================
# 2. Dynamic Database-Backed Vertical Lifecycle Management
# =============================================================================

def test_vertical_lifecycle_create_edit_disable_archive(client: TestClient, db_session: Session, admin_user: User):
    """Verifies complete non-destructive lifecycle of Verticals via Admin API."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]
    vert_name = f"Athletics Division {suffix}"

    # 1. Create Vertical
    create_resp = client.post(
        "/api/v1/admin/organization/verticals",
        json={"name": vert_name, "description": "Track and field operations"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    vert_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "ACTIVE"

    # 2. Edit Vertical
    patch_resp = client.patch(
        f"/api/v1/admin/organization/verticals/{vert_id}",
        json={"description": "Updated track, field, and marathon operations"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "Updated track, field, and marathon operations"

    # 3. Disable Vertical (Non-destructive)
    dis_resp = client.post(
        f"/api/v1/admin/organization/verticals/{vert_id}/disable",
        headers=headers,
    )
    assert dis_resp.status_code == 200
    assert dis_resp.json()["status"] == "DISABLED"

    # 4. Attempt to assign user to disabled vertical (Must Fail)
    user_service = UserService(db_session)
    test_u = user_service.create_user(
        UserCreate(username=f"vert_u_{suffix}", full_name="Vert User", password="SecurePassword123!")
    )
    db_session.commit()

    assign_resp = client.post(
        f"/api/v1/admin/users/{test_u.id}/verticals",
        json={"assignments": [{"vertical_id": vert_id, "is_primary": True}]},
        headers=headers,
    )
    assert assign_resp.status_code in [400, 422]

    # 5. Archive Vertical (Non-destructive)
    arch_resp = client.post(
        f"/api/v1/admin/organization/verticals/{vert_id}/archive",
        headers=headers,
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "ARCHIVED"

    # 6. Fresh Session Database Truth
    fresh_db = SessionLocal()
    try:
        db_vert = fresh_db.get(Vertical, uuid.UUID(vert_id))
        assert db_vert is not None
        assert db_vert.status == VerticalStatus.ARCHIVED
        assert db_vert.name == vert_name
    finally:
        fresh_db.close()


def test_remove_user_from_vertical_non_destructive(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies removing user from vertical does not delete user entity."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]

    user = user_service.create_user(
        UserCreate(
            username=f"rem_u_{suffix}",
            full_name="Remove Assignment User",
            password="SecurePassword123!",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    # Remove user from vertical
    del_resp = client.delete(
        f"/api/v1/admin/users/{user.id}/verticals/{test_vertical.id}",
        headers=headers,
    )
    assert del_resp.status_code == 200

    # Fresh session verify: User still exists, assignment removed
    fresh_db = SessionLocal()
    try:
        db_u = fresh_db.get(User, user.id)
        assert db_u is not None
        assert db_u.account_status == AccountStatus.ACTIVE
        assignment = fresh_db.scalar(
            select(UserVertical).where(UserVertical.user_id == user.id, UserVertical.vertical_id == test_vertical.id)
        )
        assert assignment is None
    finally:
        fresh_db.close()


# =============================================================================
# 3. Internal User vs Event Team User Account & Profile Separation
# =============================================================================

def test_internal_vs_event_team_creation_and_profile_linkage(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Event Team account and operational profile creation linked to an Event."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    today = date.today()
    suffix = uuid.uuid4().hex[:6]

    # Create Event
    event = Event(
        name=f"Inter-State Hockey League {suffix}",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=today + timedelta(days=20),
        created_by_id=admin_user.id,
    )
    db_session.add(event)
    db_session.commit()

    # Create Event Team Account & Profile
    payload = {
        "username": f"team_alpha_{suffix}",
        "password": "SecurePassword123!",
        "email": f"team_alpha_{suffix}@societies.org",
        "event_id": str(event.id),
        "team_name": "Phoenix Hockey Society",
        "head_name": "Rajesh Sharma",
        "head_email": "rajesh@phoenix.org",
        "head_phone": "+91 9876543210",
        "members_summary": [{"name": "Rajesh", "role": "Captain"}, {"name": "Amit", "role": "Manager"}],
        "contact_info": {"emergency_contact": "+91 9123456780", "city": "Mumbai"},
        "notes": "Registered 16 players for championship.",
    }
    resp = client.post("/api/v1/event-teams", json=payload, headers=headers)
    assert resp.status_code == 201
    team_data = resp.json()

    assert team_data["team_name"] == "Phoenix Hockey Society"
    assert team_data["event_id"] == str(event.id)
    assert team_data["head_name"] == "Rajesh Sharma"
    assert len(team_data["members_summary"]) == 2

    # Fresh session verification
    fresh_db = SessionLocal()
    try:
        db_prof = fresh_db.get(EventTeamProfile, uuid.UUID(team_data["id"]))
        assert db_prof is not None
        assert db_prof.team_name == "Phoenix Hockey Society"
        assert db_prof.event_id == event.id
        assert db_prof.user.account_status == AccountStatus.ACTIVE
    finally:
        fresh_db.close()


# =============================================================================
# 4. Event-Specific POC Group Management & Governance
# =============================================================================

def test_poc_group_assignment_enforces_one_head_poc_and_vertical_scoping(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies POC group assignment: exactly 1 active Head POC + vertical-assigned POC members."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_service = UserService(db_session)
    suffix = uuid.uuid4().hex[:6]
    today = date.today()

    # Create 2 users in test_vertical
    head_poc = user_service.create_user(
        UserCreate(username=f"hpoc_{suffix}", full_name="Head POC User", password="SecurePassword123!", vertical_ids=[test_vertical.id])
    )
    poc_member = user_service.create_user(
        UserCreate(username=f"pocm_{suffix}", full_name="POC Member User", password="SecurePassword123!", vertical_ids=[test_vertical.id])
    )

    # Create 1 user in a DIFFERENT vertical
    other_vert = Vertical(name=f"Other Vert {suffix}", organization_id=test_vertical.organization_id, status=VerticalStatus.ACTIVE)
    db_session.add(other_vert)
    db_session.flush()
    unassigned_user = user_service.create_user(
        UserCreate(username=f"unass_{suffix}", full_name="Unassigned User", password="SecurePassword123!", vertical_ids=[other_vert.id])
    )

    # Create Event
    event = Event(
        name=f"National Badminton Open {suffix}",
        vertical_id=test_vertical.id,
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date=today + timedelta(days=30),
        created_by_id=admin_user.id,
    )
    db_session.add(event)
    db_session.commit()

    # 1. Assign valid POC Group
    poc_payload = {
        "head_poc_id": str(head_poc.id),
        "poc_member_ids": [str(poc_member.id)],
        "notes": "Primary coordination team for Badminton Open",
    }
    resp = client.post(f"/api/v1/events/{event.id}/poc-group", json=poc_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["head_poc"]["user_id"] == str(head_poc.id)
    assert len(data["poc_members"]) == 1
    assert data["poc_members"][0]["user_id"] == str(poc_member.id)
    assert data["total_poc_count"] == 2

    # 2. Attempt POC Group assignment with user NOT in event vertical (Must Fail)
    invalid_payload = {
        "head_poc_id": str(unassigned_user.id),
        "poc_member_ids": [],
    }
    inv_resp = client.post(f"/api/v1/events/{event.id}/poc-group", json=invalid_payload, headers=headers)
    assert inv_resp.status_code in [400, 422]

    # 3. Fresh session read
    fresh_db = SessionLocal()
    try:
        db_ev = fresh_db.get(Event, event.id)
        assert db_ev.primary_poc_id == head_poc.id
        poc_members = fresh_db.scalars(
            select(EventMember).where(EventMember.event_id == event.id, EventMember.role_in_event == EventMemberRole.POC)
        ).all()
        assert len(poc_members) == 2
    finally:
        fresh_db.close()


# =============================================================================
# 5. Event Team Strict Operational Isolation
# =============================================================================

def test_event_team_isolation_blocks_internal_data_access(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """
    CRITICAL SECURITY TEST: Event Team account MUST NOT access internal OMS environment:
    - Internal user list
    - Internal audit logs
    - Unrelated Event Teams
    """
    today = date.today()
    suffix = uuid.uuid4().hex[:6]

    # Create Event A & Event Team A
    event_a = Event(name=f"Event A {suffix}", vertical_id=test_vertical.id, planned_date=today, created_by_id=admin_user.id)
    # Create Event B & Event Team B
    event_b = Event(name=f"Event B {suffix}", vertical_id=test_vertical.id, planned_date=today, created_by_id=admin_user.id)
    db_session.add_all([event_a, event_b])
    db_session.commit()

    team_service = EventTeamService(db_session)
    team_a = team_service.create_event_team(
        EventTeamCreate(username=f"team_a_{suffix}", password="SecurePassword123!", event_id=event_a.id, team_name="Team Alpha"),
        actor_id=admin_user.id,
    )
    team_b = team_service.create_event_team(
        EventTeamCreate(username=f"team_b_{suffix}", password="SecurePassword123!", event_id=event_b.id, team_name="Team Beta"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    headers_a = _login_and_get_token(client, f"team_a_{suffix}", "SecurePassword123!")

    # 1. Event Team A accesses own profile (Allowed)
    self_resp = client.get("/api/v1/event-teams/me", headers=headers_a)
    assert self_resp.status_code == 200
    assert self_resp.json()["team_name"] == "Team Alpha"

    # 2. Event Team A attempts to view Team B profile (Blocked)
    tamper_resp = client.get(f"/api/v1/event-teams/{team_b.id}", headers=headers_a)
    assert tamper_resp.status_code == 403, "Event Team must not access other Event Teams"

    # 3. Event Team A attempts to view internal user directory (Blocked)
    users_resp = client.get("/api/v1/admin/users", headers=headers_a)
    assert users_resp.status_code == 403, "Event Team must not access internal user directory"

    # 4. Event Team A attempts to view internal audit logs (Blocked)
    audit_resp = client.get("/api/v1/admin/audit-logs", headers=headers_a)
    assert audit_resp.status_code == 403, "Event Team must not access internal audit center"
