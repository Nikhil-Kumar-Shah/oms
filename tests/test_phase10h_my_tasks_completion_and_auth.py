"""
Phase 10H - My Tasks Completion & Secure Navigation Backend Verification Suite
Validates:
1. Create My Task -> appears in My Tasks (active tasks projection in /workspace/my-work).
2. Complete My Task -> moves to Completed Tasks (completed_tasks projection in /workspace/my-work).
3. Completed task remains accessible to its owner via GET /api/v1/tasks/{id}.
4. Created by Me returns only tasks where assigned_by_id == current_user.id.
5. Direct task UUID access cannot bypass task authorization:
   - Volunteer cannot view peer volunteer's task in same vertical (returns 403).
   - Volunteer cannot view cross-vertical task (returns 403).
6. Completed status cannot bypass task authorization (completed task still returns 403 for unauthorized peer).
7. Master Tasks catalog endpoint (GET /api/v1/tasks) strictly requires tasks.read permission,
   ensuring volunteers cannot list or access Master Tasks catalog.
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

_phase10h_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10h_sessions.get(user.id)
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
        name=f"Cricket Ops 10H {uid}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_football = Vertical(
        organization_id=org.id,
        name=f"Football Ops 10H {uid}",
        description="Football Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_cricket, v_football])
    db_session.flush()

    r_admin = db_session.query(Role).filter_by(name="ADMIN").first()
    r_coord = db_session.query(Role).filter_by(name="COORDINATOR").first()
    r_vol = db_session.query(Role).filter_by(name="VOLUNTEER").first()

    u_admin = User(
        username=f"admin_10h_{uid}",
        email=f"admin_10h_{uid}@test.oms",
        full_name="Admin 10H",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_coord_cricket = User(
        username=f"coord_cric_10h_{uid}",
        email=f"coord_cric_10h_{uid}@test.oms",
        full_name="Coord Cricket 10H",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol1_cricket = User(
        username=f"vol1_cric_10h_{uid}",
        email=f"vol1_cric_10h_{uid}@test.oms",
        full_name="Vol1 Cricket 10H",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol2_cricket = User(
        username=f"vol2_cric_10h_{uid}",
        email=f"vol2_cric_10h_{uid}@test.oms",
        full_name="Vol2 Cricket 10H",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )
    u_vol_football = User(
        username=f"vol_foot_10h_{uid}",
        email=f"vol_foot_10h_{uid}@test.oms",
        full_name="Vol Football 10H",
        password_hash="fakehash",
        account_status=AccountStatus.ACTIVE,
    )

    db_session.add_all([u_admin, u_coord_cricket, u_vol1_cricket, u_vol2_cricket, u_vol_football])
    db_session.flush()

    db_session.add_all([
        UserRole(user_id=u_admin.id, role_id=r_admin.id),
        UserRole(user_id=u_coord_cricket.id, role_id=r_coord.id),
        UserRole(user_id=u_vol1_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_vol2_cricket.id, role_id=r_vol.id),
        UserRole(user_id=u_vol_football.id, role_id=r_vol.id),
    ])

    db_session.add_all([
        UserVertical(user_id=u_coord_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_vol1_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_vol2_cricket.id, vertical_id=v_cricket.id, is_primary=True),
        UserVertical(user_id=u_vol_football.id, vertical_id=v_football.id, is_primary=True),
    ])

    # Create active sessions
    for u in [u_admin, u_coord_cricket, u_vol1_cricket, u_vol2_cricket, u_vol_football]:
        raw_tok = generate_session_token()
        _phase10h_sessions[u.id] = raw_tok
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(raw_tok),
            ip_address="127.0.0.1",
            user_agent="pytest",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add(sess)

    db_session.commit()

    return {
        "admin": u_admin,
        "coord_cric": u_coord_cricket,
        "vol1_cric": u_vol1_cricket,
        "vol2_cric": u_vol2_cricket,
        "vol_foot": u_vol_football,
        "v_cricket": v_cricket,
        "v_football": v_football,
    }


def test_my_task_creation_and_completion_lifecycle(client: TestClient, env):
    """
    1. Volunteer creates self task -> appears in My Tasks (tasks)
    2. Volunteer marks complete -> moves to Completed Tasks (completed_tasks)
    3. Volunteer can still view the completed task details
    """
    vol1 = env["vol1_cric"]

    # 1. Create Self Task
    res = client.post(
        "/api/v1/tasks/self",
        headers=_auth_headers(vol1),
        json={
            "title": "Prepare Pitch Inspection Report",
            "description": "Inspect turf density and bounce",
            "task_type": "DOCUMENTATION",
            "priority": "HIGH",
        },
    )
    assert res.status_code == 201, res.text
    task_id = res.json()["id"]

    # Check My Work: should be in active tasks and active_tasks counter == 1
    my_work = client.get("/api/v1/workspace/my-work", headers=_auth_headers(vol1)).json()
    active_ids = [t["id"] for t in my_work["tasks"]]
    completed_ids = [t["id"] for t in my_work["completed_tasks"]]
    assert task_id in active_ids
    assert task_id not in completed_ids
    assert my_work["stats"]["active_tasks"] >= 1
    assert my_work["stats"]["completed_tasks"] == 0

    # 2. Mark Complete via Transition
    res_trans = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        headers=_auth_headers(vol1),
        json={
            "status": "COMPLETED",
            "completion_percentage": 100,
        },
    )
    assert res_trans.status_code == 200, res_trans.text

    # Check My Work: must move from tasks to completed_tasks
    my_work_after = client.get("/api/v1/workspace/my-work", headers=_auth_headers(vol1)).json()
    active_ids_after = [t["id"] for t in my_work_after["tasks"]]
    completed_ids_after = [t["id"] for t in my_work_after["completed_tasks"]]

    assert task_id not in active_ids_after, "Task must not remain in active tasks"
    assert task_id in completed_ids_after, "Task must move to completed tasks"
    assert my_work_after["stats"]["completed_tasks"] >= 1

    # 3. Completed task remains accessible to owner
    res_detail = client.get(f"/api/v1/tasks/{task_id}", headers=_auth_headers(vol1))
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == task_id
    assert res_detail.json()["status"] == "COMPLETED"


def test_created_by_me_separation(client: TestClient, env):
    """
    Tasks delegated by Coordinator to Volunteer appear in:
    - Volunteer's active tasks (tasks)
    - Coordinator's created_by_me_tasks
    And does NOT appear in Volunteer's created_by_me_tasks.
    """
    coord = env["coord_cric"]
    vol1 = env["vol1_cric"]

    # Coordinator delegates a task to vol1
    res = client.post(
        "/api/v1/tasks",
        headers=_auth_headers(coord),
        json={
            "title": "Clean Pavilion Storage",
            "vertical_id": str(env["v_cricket"].id),
            "assigned_to_id": str(vol1.id),
            "priority": "MEDIUM",
            "task_type": "ROUTINE",
        },
    )
    assert res.status_code == 201, res.text
    delegated_task_id = res.json()["id"]

    # Check Coordinator's workspace: must be in created_by_me_tasks
    coord_work = client.get("/api/v1/workspace/my-work", headers=_auth_headers(coord)).json()
    coord_created_ids = [t["id"] for t in coord_work["created_by_me_tasks"]]
    assert delegated_task_id in coord_created_ids
    assert coord_work["stats"]["created_by_me_tasks"] >= 1

    # Check Volunteer's workspace: must be in tasks, NOT in created_by_me_tasks
    vol_work = client.get("/api/v1/workspace/my-work", headers=_auth_headers(vol1)).json()
    vol_active_ids = [t["id"] for t in vol_work["tasks"]]
    vol_created_ids = [t["id"] for t in vol_work["created_by_me_tasks"]]
    assert delegated_task_id in vol_active_ids
    assert delegated_task_id not in vol_created_ids


def test_direct_task_uuid_authorization_isolation(client: TestClient, env):
    """
    Object-level security:
    - Volunteer cannot view peer volunteer's task even with exact UUID (returns 403)
    - Volunteer cannot view cross-vertical task (returns 403)
    - Completed status cannot bypass authorization
    """
    vol1 = env["vol1_cric"]
    vol2 = env["vol2_cric"]
    vol_foot = env["vol_foot"]

    # vol1 creates a task
    res = client.post(
        "/api/v1/tasks/self",
        headers=_auth_headers(vol1),
        json={
            "title": "Vol1 Private Self Task",
            "priority": "LOW",
        },
    )
    assert res.status_code == 201
    vol1_task_id = res.json()["id"]

    # vol2 (same vertical!) tries to read vol1's task by knowing the UUID
    res_peer = client.get(f"/api/v1/tasks/{vol1_task_id}", headers=_auth_headers(vol2))
    assert res_peer.status_code == 403, f"Expected 403 for peer volunteer, got {res_peer.status_code}"

    # vol_foot (different vertical!) tries to read vol1's task by knowing the UUID
    res_cross = client.get(f"/api/v1/tasks/{vol1_task_id}", headers=_auth_headers(vol_foot))
    assert res_cross.status_code == 403, f"Expected 403 for cross-vertical volunteer, got {res_cross.status_code}"

    # vol1 marks complete
    client.post(
        f"/api/v1/tasks/{vol1_task_id}/transition",
        headers=_auth_headers(vol1),
        json={"status": "COMPLETED", "completion_percentage": 100},
    )

    # Completed status MUST NOT bypass authorization
    res_peer_after = client.get(f"/api/v1/tasks/{vol1_task_id}", headers=_auth_headers(vol2))
    assert res_peer_after.status_code == 403, "Completed status must not bypass object authorization"


def test_volunteer_cannot_access_master_tasks_catalog(client: TestClient, env):
    """
    GET /api/v1/tasks is protected by tasks.read.
    Volunteers must receive 403 Forbidden.
    Admins must receive 200 OK.
    """
    vol1 = env["vol1_cric"]
    admin = env["admin"]

    # Volunteer attempting to access Master Tasks catalog
    res_vol = client.get("/api/v1/tasks", headers=_auth_headers(vol1))
    assert res_vol.status_code == 403, f"Volunteers must not access /tasks catalog, got {res_vol.status_code}"

    # Admin accessing Master Tasks catalog
    res_admin = client.get("/api/v1/tasks", headers=_auth_headers(admin))
    assert res_admin.status_code == 200, f"Admin must access /tasks catalog, got {res_admin.status_code}"
