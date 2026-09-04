"""
Phase 10G - Master Task & My Task UI and Universal Audience Selector Test Suite
Validates:
1. Master Task creation using a selected user (user_ids)
2. Master Task creation using a selected vertical (vertical_ids)
3. Multiple-user selection from Universal Selector (dispatching multiple tasks)
4. Multiple-vertical selection from Universal Selector (dispatching unassigned tasks per vertical)
5. My Task creation via POST /api/v1/tasks/self and is_self_task: true
6. Confirm My Task automatically assigns to current_user (ignores client spoofing)
7. Downward delegation authority checks preserved
8. Cross-vertical isolation preserved
9. Empty string optional fields do not fail validation
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
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User

_phase10g_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10g_sessions.get(user.id)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env(db_session: Session):
    """Sets up an isolated testing environment with Admin, Coordinators, Volunteers, and Verticals."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org", code="PARADOX")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

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

    r_admin = db_session.query(Role).filter_by(name="ADMIN").first()
    r_core = db_session.query(Role).filter_by(name="SPORTS_CORE").first()
    r_coord = db_session.query(Role).filter_by(name="COORDINATOR").first()
    r_vol = db_session.query(Role).filter_by(name="VOLUNTEER").first()

    u_admin = User(
        username=f"admin_p10g_{uid}",
        email=f"admin_p10g_{uid}@test.oms",
        full_name="Admin P10G",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_cricket = User(
        username=f"coord_cric_10g_{uid}",
        email=f"coord_cric_10g_{uid}@test.oms",
        full_name="Coord Cricket 10G",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol1_cricket = User(
        username=f"vol1_cric_10g_{uid}",
        email=f"vol1_cric_10g_{uid}@test.oms",
        full_name="Vol1 Cricket 10G",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol2_cricket = User(
        username=f"vol2_cric_10g_{uid}",
        email=f"vol2_cric_10g_{uid}@test.oms",
        full_name="Vol2 Cricket 10G",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_football = User(
        username=f"coord_foot_10g_{uid}",
        email=f"coord_foot_10g_{uid}@test.oms",
        full_name="Coord Football 10G",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )

    db_session.add_all([u_admin, u_coord_cricket, u_vol1_cricket, u_vol2_cricket, u_coord_football])
    db_session.flush()

    db_session.add_all([
        UserRole(user_id=u_admin.id, role_id=r_admin.id),
        UserRole(user_id=u_coord_cricket.id, role_id=r_coord.id),
        UserRole(user_id=u_vol1_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_vol2_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_coord_football.id, role_id=r_coord.id),
    ])

    db_session.add_all([
        UserVertical(user_id=u_coord_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_vol1_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_vol2_cricket.id, vertical_id=v_cricket.id),
        UserVertical(user_id=u_coord_football.id, vertical_id=v_football.id),
    ])

    for u in [u_admin, u_coord_cricket, u_vol1_cricket, u_vol2_cricket, u_coord_football]:
        raw_tok = generate_session_token()
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ip_address="127.0.0.1",
        )
        db_session.add(sess)
        _phase10g_sessions[u.id] = raw_tok

    db_session.commit()

    return {
        "admin": u_admin,
        "coord_cricket": u_coord_cricket,
        "vol1_cricket": u_vol1_cricket,
        "vol2_cricket": u_vol2_cricket,
        "coord_football": u_coord_football,
        "v_cricket": v_cricket,
        "v_football": v_football,
    }


# =============================================================================
# 1. Master Task Creation with Universal Audience Selector Output
# =============================================================================

def test_master_task_creation_single_user_selection(client: TestClient, env: dict):
    """
    1. Master Task creation using a selected user from Universal Selector.
    - Payload contains user_ids: [vol1.id], vertical_ids: [v_cricket.id]
    - Verifies task created and assigned to the selected user.
    """
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Inspect Cricket Equipment",
        "description": "Ensure pitch rollers and stumps are functional",
        "user_ids": [str(env["vol1_cricket"].id)],
        "vertical_ids": [str(env["v_cricket"].id)],
        "priority": "HIGH",
        "task_type": "ROUTINE",
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["title"] == "Inspect Cricket Equipment"
    assert data["assigned_to_id"] == str(env["vol1_cricket"].id)
    assert data["assigned_by_id"] == str(env["coord_cricket"].id)
    assert data["vertical_id"] == str(env["v_cricket"].id)


def test_master_task_creation_single_vertical_selection(client: TestClient, env: dict):
    """
    2. Master Task creation using a selected vertical (unassigned).
    - Payload contains vertical_ids: [v_cricket.id] without users.
    - Verifies unassigned task created for that vertical.
    """
    headers = _auth_headers(env["admin"])
    payload = {
        "title": "Publish Pitch Protocol",
        "vertical_ids": [str(env["v_cricket"].id)],
        "priority": "MEDIUM",
        "task_type": "DOCUMENTATION",
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["title"] == "Publish Pitch Protocol"
    assert data["assigned_to_id"] is None
    assert data["vertical_id"] == str(env["v_cricket"].id)


def test_master_task_creation_multiple_user_selection(
    client: TestClient, db_session: Session, env: dict
):
    """
    3. Multiple-user selection from Universal Selector.
    - Payload contains user_ids: [vol1.id, vol2.id].
    - Verifies individual task records created in database for each user.
    """
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Mandatory Safety Briefing",
        "user_ids": [str(env["vol1_cricket"].id), str(env["vol2_cricket"].id)],
        "vertical_ids": [str(env["v_cricket"].id)],
        "priority": "HIGH",
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text

    # Verify both task records exist in the database
    tasks_vol1 = db_session.scalars(
        select(Task).where(
            Task.title == "Mandatory Safety Briefing",
            Task.assigned_to_id == env["vol1_cricket"].id,
        )
    ).all()
    tasks_vol2 = db_session.scalars(
        select(Task).where(
            Task.title == "Mandatory Safety Briefing",
            Task.assigned_to_id == env["vol2_cricket"].id,
        )
    ).all()

    assert len(tasks_vol1) == 1
    assert len(tasks_vol2) == 1


def test_master_task_creation_multiple_vertical_selection(
    client: TestClient, db_session: Session, env: dict
):
    """
    4. Multiple-vertical selection from Universal Selector.
    - Payload contains vertical_ids: [v_cricket.id, v_football.id].
    - Verifies unassigned tasks created across both verticals.
    """
    headers = _auth_headers(env["admin"])
    payload = {
        "title": "Q3 Budget Audit",
        "vertical_ids": [str(env["v_cricket"].id), str(env["v_football"].id)],
        "priority": "CRITICAL",
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text

    tasks_cric = db_session.scalars(
        select(Task).where(Task.title == "Q3 Budget Audit", Task.vertical_id == env["v_cricket"].id)
    ).all()
    tasks_foot = db_session.scalars(
        select(Task).where(Task.title == "Q3 Budget Audit", Task.vertical_id == env["v_football"].id)
    ).all()

    assert len(tasks_cric) == 1
    assert len(tasks_foot) == 1


# =============================================================================
# 2. My Task Creation & Server-Enforced Identity
# =============================================================================

def test_create_my_task_self_assigned(client: TestClient, env: dict):
    """
    5. My Task creation from My Tasks workspace.
    - Uses POST /api/v1/tasks/self and is_self_task: true.
    - Automatically assigns task to current_user.id.
    """
    headers = _auth_headers(env["vol1_cricket"])
    payload = {
        "title": "Review volunteer shift calendar",
        "vertical_id": str(env["v_cricket"].id),
        "priority": "LOW",
    }

    res = client.post("/api/v1/tasks/self", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["title"] == "Review volunteer shift calendar"
    assert data["assigned_to_id"] == str(env["vol1_cricket"].id)
    assert data["assigned_by_id"] == str(env["vol1_cricket"].id)


def test_create_my_task_ignores_client_assignee_spoofing(client: TestClient, env: dict):
    """
    6. Confirm My Task automatically assigns to current_user, ignoring spoofed client assigned_to_id.
    """
    headers = _auth_headers(env["vol1_cricket"])
    payload = {
        "title": "Spoofed Self Task",
        "vertical_id": str(env["v_cricket"].id),
        "is_self_task": True,
        "assigned_to_id": str(env["vol2_cricket"].id),  # Malicious attempt to spoof assignee
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["assigned_to_id"] == str(env["vol1_cricket"].id)  # Server enforced


# =============================================================================
# 3. Security, Hierarchy & Sanitization Tests
# =============================================================================

def test_downward_delegation_authority_preserved(client: TestClient, env: dict):
    """
    7. Authority check: Volunteers cannot assign tasks to other users via Universal Selector.
    """
    headers = _auth_headers(env["vol1_cricket"])
    payload = {
        "title": "Unauthorized Assignment",
        "user_ids": [str(env["coord_cricket"].id)],
        "vertical_ids": [str(env["v_cricket"].id)],
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 403


def test_cross_vertical_isolation_preserved(client: TestClient, env: dict):
    """
    8. Authority check: Coordinator cannot create tasks in or assign to unrelated verticals.
    """
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Cross Vertical Leak",
        "vertical_ids": [str(env["v_football"].id)],
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 403


def test_empty_string_optional_fields_do_not_fail(client: TestClient, env: dict):
    """
    9. Empty strings in optional fields are sanitized to None.
    """
    headers = _auth_headers(env["coord_cricket"])
    payload = {
        "title": "Empty String Test",
        "vertical_ids": [str(env["v_cricket"].id)],
        "description": "",
        "deadline": "",
        "blockers": "",
        "remarks": "",
        "evidence_link": "",
    }

    res = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["description"] is None
    assert data["deadline"] is None
    assert data["blockers"] is None


def test_my_work_returns_task_type_and_canonical_attributes(client: TestClient, env: dict):
    """
    10. GET /api/v1/workspace/my-work returns task_type, priority, status, health.
    """
    headers = _auth_headers(env["vol1_cricket"])

    # Create self-task with task_type = EVENT
    create_payload = {
        "title": "Matchday Setup",
        "task_type": "EVENT",
        "priority": "HIGH",
    }
    create_res = client.post("/api/v1/tasks/self", json=create_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text

    # Fetch /my-work
    res = client.get("/api/v1/workspace/my-work", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    task_match = next((t for t in data["tasks"] if t["title"] == "Matchday Setup"), None)
    assert task_match is not None
    assert task_match["task_type"] == "EVENT"
    assert task_match["priority"] == "HIGH"
    assert task_match["status"] in ["NOT_STARTED", "IN_PROGRESS"]
    assert task_match["health"] in ["ON_TRACK", "AT_RISK", "OVERDUE", "BLOCKED", "COMPLETE"]


def test_task_status_transitions_all_canonical_statuses(client: TestClient, env: dict):
    """
    11. Task transition endpoint supports all canonical statuses:
    NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETED, CANCELLED.
    """
    headers = _auth_headers(env["coord_cricket"])

    # Create initial task
    create_payload = {
        "title": "Comprehensive Status Lifecycle",
        "vertical_ids": [str(env["v_cricket"].id)],
        "user_ids": [str(env["coord_cricket"].id)],
        "task_type": "MILESTONE",
        "priority": "CRITICAL",
    }
    create_res = client.post("/api/v1/tasks", json=create_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text
    task_id = create_res.json()["id"]

    # 1. IN_PROGRESS
    r = client.post(f"/api/v1/tasks/{task_id}/transition", json={"status": "IN_PROGRESS", "completion_percentage": 30}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "IN_PROGRESS"
    assert r.json()["completion_percentage"] == 30

    # 2. BLOCKED
    r = client.post(f"/api/v1/tasks/{task_id}/transition", json={"status": "BLOCKED", "blockers": "Awaiting venue clearance"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "BLOCKED"
    assert r.json()["health"] == "BLOCKED"

    # 3. NOT_STARTED
    r = client.post(f"/api/v1/tasks/{task_id}/transition", json={"status": "NOT_STARTED"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "NOT_STARTED"
    assert r.json()["completion_percentage"] == 0

    # 4. COMPLETED
    r = client.post(f"/api/v1/tasks/{task_id}/transition", json={"status": "COMPLETED"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"
    assert r.json()["completion_percentage"] == 100
    assert r.json()["health"] == "COMPLETE"

    # 5. CANCELLED
    r = client.post(f"/api/v1/tasks/{task_id}/transition", json={"status": "CANCELLED"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CANCELLED"

