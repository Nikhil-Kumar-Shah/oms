"""
Phase 3: Event + Event Team Operations Test Suite
Paradox Sports OMS - Authoritative Product Specification Verification

Verifies:
1. Event Model Creation & Default Readiness Checkpoints Initialization
2. Strict Authoritative Event Lifecycle State Machine & Invalid Transition Rejection
3. POC Group Governance (Exactly 1 Active Head POC & Vertical Validation)
4. Event Team Account & Profile Management with POC Attention Notifications
5. Cross-Event Isolation & IDOR Rejection (Event Team A cannot access Event B)
6. Event Team IDOR Rejection on Unrelated Event Team Profiles
7. Event Team Blocked from Internal Privileges & Endpoints (Audit, Admin Users, Event Creation, Transition, POC Assignment)
8. Event Operational Dashboard Information Boundary Filtering (Sensitive/Confidential Data Stripping)
9. Fresh-Session PostgreSQL Persistence Truth
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
from app.models.communication import Notification, NotificationType
from app.models.event import (
    Event,
    EventMember,
    EventMemberRole,
    EventMemberStatus,
    EventReadinessItem,
    EventStatus,
    EventTeamProfile,
    EventType,
    ReadinessCategory,
    ReadinessStatus,
)
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.schemas.event import (
    EventCreate,
    EventReadinessUpdate,
    EventTransitionRequest,
    EventUpdate,
    POCGroupAssignRequest,
)
from app.schemas.event_team import EventTeamCreate, EventTeamUpdate
from app.schemas.issue import IssueCreate
from app.schemas.user import UserCreate
from app.services.event_service import EventService
from app.services.event_team_service import EventTeamService
from app.services.issue_service import IssueService
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService


def _login_and_get_token(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    RateLimitingMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["session"]["token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Event Model Creation & Default Readiness Checkpoints
# =============================================================================

def test_event_creation_and_default_readiness_checkpoints(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies event creation and automatic initialization of 8 default readiness checkpoints."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    suffix = uuid.uuid4().hex[:6]
    planned_date = (date.today() + timedelta(days=14)).isoformat()

    payload = {
        "vertical_id": str(test_vertical.id),
        "name": f"National Badminton Open {suffix}",
        "description": "Annual badminton championship tournament",
        "event_type": "TOURNAMENT",
        "planned_date": planned_date,
        "location": "Main Sports Complex, Court 1-4",
        "society_name": "Badminton Association",
    }
    create_resp = client.post("/api/v1/events", json=payload, headers=headers)
    assert create_resp.status_code == 201
    event_data = create_resp.json()
    event_id = event_data["id"]

    assert event_data["status"] == "PLANNING"
    assert event_data["name"] == f"National Badminton Open {suffix}"

    # Verify readiness checkpoints
    readiness_resp = client.get(f"/api/v1/events/{event_id}/readiness", headers=headers)
    assert readiness_resp.status_code == 200
    checkpoints = readiness_resp.json()
    assert len(checkpoints) == 8
    categories = {c["category"] for c in checkpoints}
    expected_categories = {
        "PLANNING",
        "COORDINATION",
        "DOCUMENTATION",
        "COMMUNICATIONS",
        "TECHNICAL_PREPARATION",
        "MOCK_TRIAL",
        "FINAL_APPROVAL",
        "EXECUTION_READINESS",
    }
    assert categories == expected_categories


# =============================================================================
# 2. Event Lifecycle State Machine & Invalid Transition Rejection
# =============================================================================

def test_event_lifecycle_state_machine_and_invalid_transitions(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies strict state machine transitions: PLANNING -> IN_PROGRESS -> COMPLETED -> ARCHIVED."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    event_svc = EventService(db_session)
    suffix = uuid.uuid4().hex[:6]

    event = event_svc.create_event(
        EventCreate(
            vertical_id=test_vertical.id,
            name=f"State Machine Event {suffix}",
            event_type=EventType.MATCH,
            planned_date=date.today() + timedelta(days=7),
        ),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Invalid transition directly from PLANNING to COMPLETED (Must Fail)
    bad_resp = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "COMPLETED"},
        headers=headers,
    )
    assert bad_resp.status_code in [400, 422]

    # 2. Valid transition: PLANNING -> IN_PROGRESS
    t1 = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "IN_PROGRESS", "remarks": "Event kicked off on schedule"},
        headers=headers,
    )
    assert t1.status_code == 200
    assert t1.json()["status"] == "IN_PROGRESS"

    # 3. Valid transition: IN_PROGRESS -> COMPLETED
    t2 = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "COMPLETED", "remarks": "Matches concluded and trophies awarded"},
        headers=headers,
    )
    assert t2.status_code == 200
    assert t2.json()["status"] == "COMPLETED"

    # 4. Valid transition: COMPLETED -> ARCHIVED
    t3 = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "ARCHIVED", "remarks": "Post-event documentation sealed"},
        headers=headers,
    )
    assert t3.status_code == 200
    assert t3.json()["status"] == "ARCHIVED"

    # 5. Invalid transition: Reverse transition from ARCHIVED to PLANNING (Must Fail)
    bad_archived = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "PLANNING"},
        headers=headers,
    )
    assert bad_archived.status_code in [400, 422]


# =============================================================================
# 3. POC Group Governance & Vertical Scoping
# =============================================================================

def test_poc_group_assignment_enforces_single_head_and_vertical_scoping(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies POC group requires 1 active Head POC and validates all members in target vertical."""
    headers = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_svc = UserService(db_session)
    event_svc = EventService(db_session)
    suffix = uuid.uuid4().hex[:6]

    # Users in test_vertical
    head_poc = user_svc.create_user(UserCreate(username=f"head_poc_{suffix}", full_name="Head POC User", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    poc_m1 = user_svc.create_user(UserCreate(username=f"poc_m1_{suffix}", full_name="POC Member 1", password="SecurePassword123!", vertical_ids=[test_vertical.id]))

    # User in outside vertical
    other_vert = Vertical(name=f"Aquatics {suffix}", organization_id=test_vertical.organization_id, status=VerticalStatus.ACTIVE)
    db_session.add(other_vert)
    db_session.flush()
    outside_user = user_svc.create_user(UserCreate(username=f"out_u_{suffix}", full_name="Outside User", password="SecurePassword123!", vertical_ids=[other_vert.id]))
    db_session.commit()

    event = event_svc.create_event(
        EventCreate(vertical_id=test_vertical.id, name=f"POC Test Event {suffix}", planned_date=date.today() + timedelta(days=5)),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Valid POC group assignment
    poc_resp = client.post(
        f"/api/v1/events/{event.id}/poc-group",
        json={
            "head_poc_id": str(head_poc.id),
            "poc_member_ids": [str(poc_m1.id)],
            "notes": "Assigned primary logistics coordination",
        },
        headers=headers,
    )
    assert poc_resp.status_code == 200
    poc_data = poc_resp.json()
    assert poc_data["head_poc"]["user_id"] == str(head_poc.id)
    assert len(poc_data["poc_members"]) == 1
    assert poc_data["poc_members"][0]["user_id"] == str(poc_m1.id)

    # 2. Invalid assignment with outside user (Must Fail)
    bad_poc = client.post(
        f"/api/v1/events/{event.id}/poc-group",
        json={
            "head_poc_id": str(outside_user.id),
            "poc_member_ids": [str(poc_m1.id)],
        },
        headers=headers,
    )
    assert bad_poc.status_code in [400, 422]


# =============================================================================
# 4. Event Team Account, Profile Update & POC Change Notifications
# =============================================================================

def test_event_team_profile_update_and_poc_notification(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Event Team profile updates and attention notification generation to POCs."""
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    user_svc = UserService(db_session)
    event_svc = EventService(db_session)
    suffix = uuid.uuid4().hex[:6]

    head_poc = user_svc.create_user(UserCreate(username=f"hpoc_notif_{suffix}", full_name="Head POC Notif", password="SecurePassword123!", vertical_ids=[test_vertical.id]))
    db_session.commit()

    event = event_svc.create_event(
        EventCreate(vertical_id=test_vertical.id, name=f"Notif Event {suffix}", primary_poc_id=head_poc.id, planned_date=date.today() + timedelta(days=10)),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Create Event Team Account & Profile
    team_payload = {
        "event_id": str(event.id),
        "team_name": f"Thunderbolts Team {suffix}",
        "username": f"team_thunder_{suffix}",
        "password": "SecurePassword123!",
        "head_name": "Captain Rogers",
        "head_email": "rogers@thunder.org",
        "head_phone": "+1999888777",
    }
    create_team_resp = client.post("/api/v1/event-teams", json=team_payload, headers=headers_admin)
    assert create_team_resp.status_code == 201
    team_data = create_team_resp.json()
    team_id = team_data["id"]

    # 2. Event Team logs in and updates profile via /me
    headers_team = _login_and_get_token(client, f"team_thunder_{suffix}", "SecurePassword123!")
    update_payload = {
        "head_name": "Captain Steve Rogers",
        "head_phone": "+1999555123",
        "members_summary": [{"name": "Player 1", "position": "Forward"}, {"name": "Player 2", "position": "Defense"}],
    }
    update_resp = client.put("/api/v1/event-teams/me", json=update_payload, headers=headers_team)
    assert update_resp.status_code == 200
    assert update_resp.json()["head_name"] == "Captain Steve Rogers"

    # 3. Verify Head POC received attention notification in database
    notif = db_session.scalar(
        select(Notification).where(
            Notification.recipient_id == head_poc.id,
            Notification.related_resource_id == uuid.UUID(team_id),
        )
    )
    assert notif is not None
    assert f"Thunderbolts Team {suffix}" in notif.title


# =============================================================================
# 5. Cross-Event Isolation & IDOR Denial
# =============================================================================

def test_event_team_cross_event_isolation_and_idor_rejection(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """
    CRITICAL SECURITY TEST:
    Event Team A associated with Event A must be FORBIDDEN from accessing Event B.
    """
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    event_svc = EventService(db_session)
    team_svc = EventTeamService(db_session)
    suffix = uuid.uuid4().hex[:6]

    # Event A & Event Team A
    event_a = event_svc.create_event(EventCreate(vertical_id=test_vertical.id, name=f"Event Alpha {suffix}", planned_date=date.today() + timedelta(days=6)), actor_id=admin_user.id)
    # Event B & Event Team B
    event_b = event_svc.create_event(EventCreate(vertical_id=test_vertical.id, name=f"Event Beta {suffix}", planned_date=date.today() + timedelta(days=8)), actor_id=admin_user.id)
    db_session.commit()

    team_a = team_svc.create_event_team(
        EventTeamCreate(event_id=event_a.id, team_name=f"Team Alpha {suffix}", username=f"team_a_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    team_b = team_svc.create_event_team(
        EventTeamCreate(event_id=event_b.id, team_name=f"Team Beta {suffix}", username=f"team_b_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    headers_team_a = _login_and_get_token(client, f"team_a_{suffix}", "SecurePassword123!")

    # 1. Team A accesses Event A (Allowed)
    r_a = client.get(f"/api/v1/events/{event_a.id}", headers=headers_team_a)
    assert r_a.status_code == 200

    # 2. Team A attempts to access Event B details (Forbidden)
    r_b = client.get(f"/api/v1/events/{event_b.id}", headers=headers_team_a)
    assert r_b.status_code == 403, "Event Team A must be forbidden from accessing Event B"

    # 3. Team A attempts to access Event B dashboard (Forbidden)
    r_dash_b = client.get(f"/api/v1/events/{event_b.id}/dashboard", headers=headers_team_a)
    assert r_dash_b.status_code == 403, "Event Team A must be forbidden from accessing Event B dashboard"

    # 4. Team A attempts to access Event B POC group (Forbidden)
    r_poc_b = client.get(f"/api/v1/events/{event_b.id}/poc-group", headers=headers_team_a)
    assert r_poc_b.status_code == 403, "Event Team A must be forbidden from accessing Event B POC group"

    # 5. Team A attempts to access Event B readiness checklist (Forbidden)
    r_ready_b = client.get(f"/api/v1/events/{event_b.id}/readiness", headers=headers_team_a)
    assert r_ready_b.status_code == 403, "Event Team A must be forbidden from accessing Event B readiness"


# =============================================================================
# 6. Event Team IDOR on Unrelated Event Team Profiles Denied
# =============================================================================

def test_event_team_idor_on_other_event_team_profiles_denied(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Event Team A cannot view or modify Event Team B's profile via direct ID substitution."""
    event_svc = EventService(db_session)
    team_svc = EventTeamService(db_session)
    suffix = uuid.uuid4().hex[:6]

    event = event_svc.create_event(EventCreate(vertical_id=test_vertical.id, name=f"Shared Tourney {suffix}", planned_date=date.today() + timedelta(days=12)), actor_id=admin_user.id)
    db_session.commit()

    team_x = team_svc.create_event_team(
        EventTeamCreate(event_id=event.id, team_name=f"Team X {suffix}", username=f"team_x_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    team_y = team_svc.create_event_team(
        EventTeamCreate(event_id=event.id, team_name=f"Team Y {suffix}", username=f"team_y_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    headers_team_x = _login_and_get_token(client, f"team_x_{suffix}", "SecurePassword123!")

    # 1. Team X reads Team X profile (Allowed)
    r_x = client.get(f"/api/v1/event-teams/{team_x.id}", headers=headers_team_x)
    assert r_x.status_code == 200

    # 2. Team X attempts to read Team Y profile (Forbidden)
    r_y = client.get(f"/api/v1/event-teams/{team_y.id}", headers=headers_team_x)
    assert r_y.status_code == 403, "Team X cannot view Team Y profile"

    # 3. Team X attempts to update Team Y profile (Forbidden)
    r_put_y = client.put(f"/api/v1/event-teams/{team_y.id}", json={"team_name": "Tampered Team Name"}, headers=headers_team_x)
    assert r_put_y.status_code == 403, "Team X cannot update Team Y profile"


# =============================================================================
# 7. Event Team Blocked from Internal Endpoints
# =============================================================================

def test_event_team_blocked_from_internal_endpoints(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Event Team accounts are strictly forbidden from internal administrative and operational endpoints."""
    event_svc = EventService(db_session)
    team_svc = EventTeamService(db_session)
    suffix = uuid.uuid4().hex[:6]

    event = event_svc.create_event(EventCreate(vertical_id=test_vertical.id, name=f"Boundary Event {suffix}", planned_date=date.today() + timedelta(days=9)), actor_id=admin_user.id)
    db_session.commit()

    team = team_svc.create_event_team(
        EventTeamCreate(event_id=event.id, team_name=f"Isolated Team {suffix}", username=f"iso_team_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    headers_team = _login_and_get_token(client, f"iso_team_{suffix}", "SecurePassword123!")

    # 1. Attempt Event Creation (Forbidden)
    r_create_evt = client.post(
        "/api/v1/events",
        json={"vertical_id": str(test_vertical.id), "name": "Rogue Event", "planned_date": date.today().isoformat()},
        headers=headers_team,
    )
    assert r_create_evt.status_code == 403

    # 2. Attempt Event Lifecycle Transition (Forbidden)
    r_trans = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "COMPLETED"},
        headers=headers_team,
    )
    assert r_trans.status_code == 403

    # 3. Attempt POC Group Assignment (Forbidden)
    r_poc = client.post(
        f"/api/v1/events/{event.id}/poc-group",
        json={"head_poc_id": str(team.user_id), "poc_member_ids": []},
        headers=headers_team,
    )
    assert r_poc.status_code == 403

    # 4. Attempt Accessing Internal Audit Log (Forbidden)
    r_audit = client.get("/api/v1/admin/audit-logs", headers=headers_team)
    assert r_audit.status_code == 403

    # 5. Attempt Accessing Internal Users Directory (Forbidden)
    r_users = client.get("/api/v1/admin/users", headers=headers_team)
    assert r_users.status_code == 403


# =============================================================================
# 8. Event Dashboard Information Boundary Filtering
# =============================================================================

def test_event_dashboard_information_boundary_filtering(client: TestClient, db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies Event Dashboard filters out internal sensitive & confidential issues when viewed by Event Team."""
    event_svc = EventService(db_session)
    team_svc = EventTeamService(db_session)
    issue_svc = IssueService(db_session)
    suffix = uuid.uuid4().hex[:6]

    # Dedicated vertical for clean isolation
    dash_vert = Vertical(name=f"Dash Vertical {suffix}", organization_id=test_vertical.organization_id, status=VerticalStatus.ACTIVE)
    db_session.add(dash_vert)
    db_session.flush()

    event = event_svc.create_event(EventCreate(vertical_id=dash_vert.id, name=f"Dash Filter Event {suffix}", planned_date=date.today() + timedelta(days=15)), actor_id=admin_user.id)
    db_session.commit()

    team = team_svc.create_event_team(
        EventTeamCreate(event_id=event.id, team_name=f"Dash Team {suffix}", username=f"dash_team_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # Create NORMAL issue and CONFIDENTIAL issue under event's vertical
    issue_norm = issue_svc.create_issue(
        IssueCreate(vertical_id=dash_vert.id, title=f"Public Water Pitcher {suffix}", description="Pitcher needed near court", sensitivity=IssueSensitivity.NORMAL),
        actor_id=admin_user.id,
    )
    issue_conf = issue_svc.create_issue(
        IssueCreate(vertical_id=dash_vert.id, title=f"Internal Financial Discrepancy {suffix}", description="Confidential prize pool issue", sensitivity=IssueSensitivity.CONFIDENTIAL),
        actor_id=admin_user.id,
    )
    db_session.commit()

    # 1. Admin views dashboard -> sees both issues
    headers_admin = _login_and_get_token(client, admin_user.username, "AdminPass@123")
    dash_admin = client.get(f"/api/v1/events/{event.id}/dashboard", headers=headers_admin)
    assert dash_admin.status_code == 200
    admin_issue_titles = [i["title"] for i in dash_admin.json()["issues"]]
    assert f"Public Water Pitcher {suffix}" in admin_issue_titles
    assert f"Internal Financial Discrepancy {suffix}" in admin_issue_titles

    # 2. Event Team views dashboard -> sees ONLY NORMAL issue, CONFIDENTIAL issue is stripped
    headers_team = _login_and_get_token(client, f"dash_team_{suffix}", "SecurePassword123!")
    dash_team = client.get(f"/api/v1/events/{event.id}/dashboard", headers=headers_team)
    assert dash_team.status_code == 200
    team_issue_titles = [i["title"] for i in dash_team.json()["issues"]]
    assert f"Public Water Pitcher {suffix}" in team_issue_titles
    assert f"Internal Financial Discrepancy {suffix}" not in team_issue_titles


# =============================================================================
# 9. Fresh Session PostgreSQL Persistence Truth
# =============================================================================

def test_phase3_fresh_session_persistence_truth(db_session: Session, admin_user: User, test_vertical: Vertical):
    """Verifies direct database truth reads across completely fresh, isolated sessions."""
    event_svc = EventService(db_session)
    team_svc = EventTeamService(db_session)
    suffix = uuid.uuid4().hex[:6]

    event = event_svc.create_event(
        EventCreate(vertical_id=test_vertical.id, name=f"Fresh Session Event {suffix}", planned_date=date.today() + timedelta(days=20)),
        actor_id=admin_user.id,
    )
    db_session.commit()
    event_id = event.id

    team = team_svc.create_event_team(
        EventTeamCreate(event_id=event_id, team_name=f"Fresh Session Team {suffix}", username=f"fresh_tm_{suffix}", password="SecurePassword123!"),
        actor_id=admin_user.id,
    )
    db_session.commit()
    team_id = team.id

    # Query using a completely fresh database session
    fresh_db = SessionLocal()
    try:
        db_event = fresh_db.get(Event, event_id)
        assert db_event is not None
        assert db_event.name == f"Fresh Session Event {suffix}"
        assert db_event.status == EventStatus.PLANNING

        db_team = fresh_db.get(EventTeamProfile, team_id)
        assert db_team is not None
        assert db_team.team_name == f"Fresh Session Team {suffix}"
        assert db_team.event_id == event_id
    finally:
        fresh_db.close()
