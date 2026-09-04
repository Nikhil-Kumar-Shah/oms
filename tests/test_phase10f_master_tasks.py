"""
Phase 10F - Master Task & My Task Workflow Refactor Test Suite
Validates unified task data model, server-authoritative self-assignment, downward delegation hierarchy,
empty string field coercions, cross-vertical isolation, and database-level view scopes (all, my_tasks, created_by_me).
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User

_phase10f_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10f_sessions.get(user.id)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def task_workflow_env(db_session: Session):
    """Sets up an isolated testing environment with Core, Coordinators, Volunteers, and Verticals."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org", code="PARADOX")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    # Verticals
    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket Ops {uid}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_football = Vertical(
        organization_id=org.id,
        name=f"Football Ops {uid}",
        description="Football Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_cricket, v_football])
    db_session.flush()

    # Roles
    r_admin = db_session.query(Role).filter_by(name="ADMIN").first()
    r_sports_core = db_session.query(Role).filter_by(name="SPORTS_CORE").first()
    r_coord = db_session.query(Role).filter_by(name="COORDINATOR").first()
    r_vol = db_session.query(Role).filter_by(name="VOLUNTEER").first()

    # Users
    u_admin = User(
        username=f"admin_p10f_{uid}",
        email=f"admin_p10f_{uid}@test.oms",
        full_name="Admin P10F",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_core = User(
        username=f"core_p10f_{uid}",
        email=f"core_p10f_{uid}@test.oms",
        full_name="Sports Core P10F",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_cricket = User(
        username=f"coord_cric_{uid}",
        email=f"coord_cric_{uid}@test.oms",
        full_name="Coord Cricket",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol_cricket = User(
        username=f"vol_cric_{uid}",
        email=f"vol_cric_{uid}@test.oms",
        full_name="Volunteer Cricket",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_football = User(
        username=f"coord_foot_{uid}",
        email=f"coord_foot_{uid}@test.oms",
        full_name="Coord Football",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )

    db_session.add_all([u_admin, u_core, u_coord_cricket, u_vol_cricket, u_coord_football])
    db_session.flush()

    # Assign Roles
    db_session.add_all([
        UserRole(user_id=u_admin.id, role_id=r_admin.id),
        UserRole(user_id=u_core.id, role_id=r_sports_core.id),
        UserRole(user_id=u_coord_cricket.id, role_id=r_coord.id),
        UserRole(user_id=u_vol_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_coord_football.id, role_id=r_coord.id),
    ])

    # Vertical memberships
    db_session.add_all([
        UserVertical(user_id=u_core.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_coord_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_vol_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_coord_football.id, vertical_id=v_football.id),
    ])

    # Generate session tokens
    for u in [u_admin, u_core, u_coord_cricket, u_vol_cricket, u_coord_football]:
        raw_tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ip_address="127.0.0.1",
        )
        db_session.add(sess)
        _phase10f_sessions[u.id] = raw_tok

    db_session.commit()

    return {
        "admin": u_admin,
        "sports_core": u_core,
        "coord_cricket": u_coord_cricket,
        "vol_cricket": u_vol_cricket,
        "coord_football": u_coord_football,
        "v_cricket": v_cricket,
        "v_football": v_football,
    }


# =============================================================================
# 1. Master Task Creation & Delegation Tests
# =============================================================================

def test_create_master_task_with_valid_assignee(client: TestClient, task_workflow_env: dict):
    """Verifies manager creating a delegated master task for a vertical subordinate succeeds."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Prepare Pitch Covers",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": str(env["vol_cricket"].id),
        "task_type": "ROUTINE",
        "priority": "HIGH",
        "description": "Inspect and deploy pitch covers before expected rain.",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Prepare Pitch Covers"
    assert body["assigned_by_id"] == str(env["coord_cricket"].id)
    assert body["assigned_to_id"] == str(env["vol_cricket"].id)
    assert body["vertical_id"] == str(env["v_cricket"].id)


def test_create_master_task_unassigned(client: TestClient, task_workflow_env: dict):
    """Verifies creating an unassigned master task succeeds."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Unassigned Pavilion Inventory",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": None,
        "task_type": "DOCUMENTATION",
        "priority": "LOW",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Unassigned Pavilion Inventory"
    assert body["assigned_by_id"] == str(env["coord_cricket"].id)
    assert body["assigned_to_id"] is None


# =============================================================================
# 2. My Task (Self-Assignment) Tests
# =============================================================================

def test_create_my_task_self_assigned(client: TestClient, task_workflow_env: dict):
    """Verifies creating a self-task sets assigned_to_id to current user."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Personal Coordinator Checklist",
        "vertical_id": str(env["v_cricket"].id),
        "is_self_task": True,
        "task_type": "ROUTINE",
        "priority": "MEDIUM",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Personal Coordinator Checklist"
    assert body["assigned_by_id"] == str(env["coord_cricket"].id)
    assert body["assigned_to_id"] == str(env["coord_cricket"].id)


def test_create_my_task_via_dedicated_endpoint(client: TestClient, task_workflow_env: dict):
    """Verifies POST /api/v1/tasks/self creates self-assigned task."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Self Scheduled Maintenance",
        "vertical_id": str(env["v_cricket"].id),
        "task_type": "ROUTINE",
        "priority": "MEDIUM",
    }
    resp = client.post("/api/v1/tasks/self", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Self Scheduled Maintenance"
    assert body["assigned_by_id"] == str(env["coord_cricket"].id)
    assert body["assigned_to_id"] == str(env["coord_cricket"].id)


def test_my_task_ignores_client_assignee_spoofing(client: TestClient, task_workflow_env: dict):
    """Verifies self-task endpoint ignores client-provided assigned_to_id and binds to caller."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Spoofed Assignee Self Task",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": str(env["vol_cricket"].id),  # Client attempts to spoof assignee
        "is_self_task": True,
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Server must override assigned_to_id to current_user.id
    assert body["assigned_to_id"] == str(env["coord_cricket"].id)


def test_volunteer_can_create_self_task_without_delegation_authority(client: TestClient, task_workflow_env: dict):
    """Verifies operational volunteers can create self-tasks without downward delegation permission."""
    env = task_workflow_env
    headers = _auth_headers(env["vol_cricket"])
    payload = {
        "title": "Volunteer Self Work Checklist",
        "vertical_id": str(env["v_cricket"].id),
        "is_self_task": True,
        "task_type": "ROUTINE",
        "priority": "LOW",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned_by_id"] == str(env["vol_cricket"].id)
    assert body["assigned_to_id"] == str(env["vol_cricket"].id)


# =============================================================================
# 3. Validation & Empty String Sanitization Tests
# =============================================================================

def test_empty_string_optional_fields_do_not_fail_validation(client: TestClient, task_workflow_env: dict):
    """
    Verifies that optional fields sent as empty strings (deadline: '', assigned_to_id: '',
    remarks: '', evidence_link: '') do NOT cause 422 or 'Invalid request parameters or payload'.
    """
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Clean Pitch Boundary",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": "",     # Empty string should be coerced to None
        "deadline": "",           # Empty string should be coerced to None
        "description": "",        # Empty string should be coerced to None
        "remarks": "",            # Empty string should be coerced to None
        "evidence_link": "",      # Empty string should be coerced to None
        "blockers": "",           # Empty string should be coerced to None
        "task_type": "ROUTINE",
        "priority": "MEDIUM",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Clean Pitch Boundary"
    assert body["assigned_to_id"] is None
    assert body["deadline"] is None
    assert body["remarks"] is None


def test_missing_required_fields_return_clear_422(client: TestClient, task_workflow_env: dict):
    """Verifies missing required fields return descriptive 422 validation errors."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])

    # Missing title
    resp1 = client.post("/api/v1/tasks", json={"vertical_id": str(env["v_cricket"].id)}, headers=headers)
    assert resp1.status_code == 422
    assert "title" in str(resp1.json()).lower()

    # Missing vertical_id
    resp2 = client.post("/api/v1/tasks", json={"title": "Valid Title"}, headers=headers)
    assert resp2.status_code == 422
    assert "vertical_id" in str(resp2.json()).lower()


# =============================================================================
# 4. Delegation Authority & Vertical Isolation Tests
# =============================================================================

def test_volunteer_cannot_assign_to_others(client: TestClient, task_workflow_env: dict):
    """Verifies volunteers cannot delegate tasks to other members."""
    env = task_workflow_env
    headers = _auth_headers(env["vol_cricket"])
    payload = {
        "title": "Volunteer Delegating Upward",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": str(env["coord_cricket"].id),
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 403, resp.text
    assert "cannot assign" in resp.json()["error"]["message"].lower()


def test_coordinator_cannot_assign_upward(client: TestClient, task_workflow_env: dict):
    """Verifies coordinators cannot delegate tasks upward to Sports Core."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Coordinator Delegating Upward",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": str(env["sports_core"].id),
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 403, resp.text
    assert "cannot assign" in resp.json()["error"]["message"].lower() or "authority" in resp.json()["error"]["message"].lower()


def test_cannot_create_task_in_unauthorized_vertical(client: TestClient, task_workflow_env: dict):
    """Verifies coordinators cannot create tasks in a vertical they are not assigned to."""
    env = task_workflow_env
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Cross Vertical Intrusion Task",
        "vertical_id": str(env["v_football"].id),  # Cricket coord is not in Football
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code == 403, resp.text
    assert "vertical division" in resp.json()["error"]["message"].lower()


def test_cannot_assign_to_user_outside_target_vertical(client: TestClient, task_workflow_env: dict):
    """Verifies cannot assign task to a user who does not belong to the target vertical."""
    env = task_workflow_env
    headers = _auth_headers(env["sports_core"])  # Executive with broad access
    payload = {
        "title": "Mismatched Vertical Assignee",
        "vertical_id": str(env["v_cricket"].id),
        "assigned_to_id": str(env["coord_football"].id),  # Football coord not in Cricket
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert resp.status_code in [400, 422], resp.text
    assert "vertical" in resp.json()["error"]["message"].lower()


# =============================================================================
# 5. Database-Level Listing & View Scope Tests
# =============================================================================

def test_tasks_list_view_scopes(client: TestClient, task_workflow_env: dict):
    """
    Verifies view scopes:
    - scope='my_tasks' strictly queries assigned_to_id == current_user.id
    - scope='created_by_me' strictly queries assigned_by_id == current_user.id
    - Delegated task from User A to User B appears in B's My Tasks, NOT in A's My Tasks
    """
    env = task_workflow_env
    headers_a = _auth_headers(env["coord_cricket"])  # User A
    headers_b = _auth_headers(env["vol_cricket"])    # User B

    # 1. User A creates delegated task for User B
    resp_del = client.post(
        "/api/v1/tasks",
        json={
            "title": "Delegated Task A to B",
            "vertical_id": str(env["v_cricket"].id),
            "assigned_to_id": str(env["vol_cricket"].id),
        },
        headers=headers_a,
    )
    assert resp_del.status_code == 201
    task_del_id = resp_del.json()["id"]

    # 2. User A creates a self-task
    resp_self = client.post(
        "/api/v1/tasks",
        json={
            "title": "Self Task of User A",
            "vertical_id": str(env["v_cricket"].id),
            "is_self_task": True,
        },
        headers=headers_a,
    )
    assert resp_self.status_code == 201
    task_self_id = resp_self.json()["id"]

    # --- Query User A's My Tasks ---
    resp_a_my = client.get("/api/v1/tasks?scope=my_tasks", headers=headers_a)
    assert resp_a_my.status_code == 200
    my_tasks_a_ids = [t["id"] for t in resp_a_my.json()["items"]]
    assert task_self_id in my_tasks_a_ids
    # Crucial: Delegated task created by A for B must NOT be in A's My Tasks!
    assert task_del_id not in my_tasks_a_ids

    # --- Query User B's My Tasks ---
    resp_b_my = client.get("/api/v1/tasks?scope=my_tasks", headers=headers_b)
    assert resp_b_my.status_code == 200
    my_tasks_b_ids = [t["id"] for t in resp_b_my.json()["items"]]
    # Delegated task MUST appear in User B's My Tasks!
    assert task_del_id in my_tasks_b_ids
    assert task_self_id not in my_tasks_b_ids

    # --- Query User A's Created by Me ---
    resp_a_created = client.get("/api/v1/tasks?scope=created_by_me", headers=headers_a)
    assert resp_a_created.status_code == 200
    created_a_ids = [t["id"] for t in resp_a_created.json()["items"]]
    assert task_del_id in created_a_ids
    assert task_self_id in created_a_ids


def test_coordinator_scoped_to_assigned_vertical(client: TestClient, task_workflow_env: dict):
    """Verifies a coordinator can only see tasks within their assigned vertical division."""
    env = task_workflow_env
    headers_cric = _auth_headers(env["coord_cricket"])
    headers_foot = _auth_headers(env["coord_football"])

    # Create task in Football
    resp_foot = client.post(
        "/api/v1/tasks",
        json={
            "title": "Football Goalpost Inspection",
            "vertical_id": str(env["v_football"].id),
            "is_self_task": True,
        },
        headers=headers_foot,
    )
    assert resp_foot.status_code == 201
    foot_task_id = resp_foot.json()["id"]

    # Cricket coordinator lists all tasks in their scope
    resp_list = client.get("/api/v1/tasks?scope=all", headers=headers_cric)
    assert resp_list.status_code == 200
    cric_task_ids = [t["id"] for t in resp_list.json()["items"]]
    # Football task must NOT be visible to Cricket coordinator
    assert foot_task_id not in cric_task_ids

    # Object-level access to Football task by Cricket coordinator must be 403 Forbidden
    resp_obj = client.get(f"/api/v1/tasks/{foot_task_id}", headers=headers_cric)
    assert resp_obj.status_code == 403
