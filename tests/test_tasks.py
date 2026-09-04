"""
Master Tasks & Personal Work (My Work) Test Suite
"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import UserVertical, Vertical
from app.models.task import TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.services.task_service import TaskService


def test_create_task_success(client: TestClient, auth_headers_admin: dict, db_session: Session, coordinator_user: User):
    """Verifies creating a task with vertical and assigned user succeeds."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    payload = {
        "vertical_id": str(vert.id),
        "assigned_to_id": str(coordinator_user.id),
        "title": "Check goalposts before tournament",
        "description": "Inspect structural integrity of stadium goalposts",
        "task_type": "ROUTINE",
        "priority": "HIGH",
        "deadline": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    }
    response = client.post("/api/v1/tasks", json=payload, headers=auth_headers_admin)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["assigned_to_username"] == coordinator_user.username
    assert data["status"] == "NOT_STARTED"
    assert data["completion_percentage"] == 0
    assert data["health"] in ["ON_TRACK", "AT_RISK"]


def test_cannot_assign_task_to_user_outside_vertical(
    client: TestClient,
    auth_headers_admin: dict,
    db_session: Session,
    regular_user: User,
):
    """Verifies assigning a task to a user who is not assigned to the vertical fails."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Cricket Operations"))
    payload = {
        "vertical_id": str(vert.id),
        "assigned_to_id": str(regular_user.id),  # regular_user is not assigned to Cricket Operations
        "title": "Inspect pitch roller",
    }
    response = client.post("/api/v1/tasks", json=payload, headers=auth_headers_admin)
    assert response.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]


def test_task_status_transitions_and_health_calc(
    client: TestClient,
    auth_headers_admin: dict,
    db_session: Session,
):
    """Verifies status transitions and completion percentage rules."""
    vert = db_session.scalar(select(Vertical).limit(1))
    task_service = TaskService(db_session)
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    # Create task
    task = task_service.create_task(
        type("TaskCreate", (), {
            "vertical_id": vert.id,
            "assigned_to_id": None,
            "title": "Scoreboard Maintenance",
            "description": None,
            "task_type": TaskType.ROUTINE,
            "priority": TaskPriority.MEDIUM,
            "deadline": datetime.now(timezone.utc) + timedelta(days=5),
            "blockers": None,
            "remarks": None,
            "evidence_link": None,
        })(),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # 1. Transition to IN_PROGRESS
    resp1 = client.post(
        f"/api/v1/tasks/{task.id}/transition",
        json={"status": "IN_PROGRESS", "completion_percentage": 40},
        headers=auth_headers_admin,
    )
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["status"] == "IN_PROGRESS"
    assert resp1.json()["completion_percentage"] == 40

    # 2. Transition to COMPLETED
    resp2 = client.post(
        f"/api/v1/tasks/{task.id}/transition",
        json={"status": "COMPLETED"},
        headers=auth_headers_admin,
    )
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["status"] == "COMPLETED"
    assert resp2.json()["completion_percentage"] == 100
    assert resp2.json()["health"] == "COMPLETE"
    assert resp2.json()["completed_on"] is not None


def test_my_work_returns_authenticated_user_tasks_only(
    client: TestClient,
    auth_headers_coordinator: dict,
    auth_headers_user: dict,
    coordinator_user: User,
    regular_user: User,
    db_session: Session,
):
    """Verifies /api/v1/my-work returns only the caller's assigned tasks and ignores spoofed user_id."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    task_service = TaskService(db_session)
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    # Create task assigned to coordinator
    task_service.create_task(
        type("TaskCreate", (), {
            "vertical_id": vert.id,
            "assigned_to_id": coordinator_user.id,
            "title": "Coordinator Private Task",
            "description": None,
            "task_type": TaskType.ROUTINE,
            "priority": TaskPriority.HIGH,
            "deadline": datetime.now(timezone.utc) + timedelta(days=1),
            "blockers": None,
            "remarks": None,
            "evidence_link": None,
        })(),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # 1. Coordinator querying /my-work receives the task
    resp_coord = client.get("/api/v1/my-work", headers=auth_headers_coordinator)
    assert resp_coord.status_code == status.HTTP_200_OK
    titles = [t["title"] for t in resp_coord.json()["items"]]
    assert "Coordinator Private Task" in titles

    # 2. Regular user querying /my-work?user_id=<coordinator_id> STILL only sees their own work!
    resp_user = client.get(
        f"/api/v1/my-work?user_id={coordinator_user.id}",
        headers=auth_headers_user,
    )
    assert resp_user.status_code == status.HTTP_200_OK
    user_titles = [t["title"] for t in resp_user.json()["items"]]
    assert "Coordinator Private Task" not in user_titles


def test_task_comments_and_history(
    client: TestClient,
    auth_headers_admin: dict,
    db_session: Session,
):
    """Verifies adding comments and checking immutable task history."""
    vert = db_session.scalar(select(Vertical).limit(1))
    task_service = TaskService(db_session)
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    task = task_service.create_task(
        type("TaskCreate", (), {
            "vertical_id": vert.id,
            "assigned_to_id": None,
            "title": "History Comment Task",
            "description": None,
            "task_type": TaskType.ROUTINE,
            "priority": TaskPriority.MEDIUM,
            "deadline": None,
            "blockers": None,
            "remarks": None,
            "evidence_link": None,
        })(),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # Add comment
    c_resp = client.post(
        f"/api/v1/tasks/{task.id}/comments",
        json={"content": "Inspection completed smoothly."},
        headers=auth_headers_admin,
    )
    assert c_resp.status_code == status.HTTP_201_CREATED
    assert c_resp.json()["content"] == "Inspection completed smoothly."

    # Check history
    h_resp = client.get(f"/api/v1/tasks/{task.id}/history", headers=auth_headers_admin)
    assert h_resp.status_code == status.HTTP_200_OK
    history_items = h_resp.json()
    assert len(history_items) >= 1
    assert any(h["action"] == "TASK_CREATED" for h in history_items)
