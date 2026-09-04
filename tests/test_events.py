"""
Events, Event Teams & Readiness Test Suite
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.event import EventStatus, EventType, ReadinessStatus
from app.models.organization import Vertical
from app.models.user import User


def test_create_event_and_readiness_checkpoints(
    client: TestClient,
    auth_headers_admin: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Verifies creating an event and checks automatic initialization of readiness checkpoints."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    payload = {
        "vertical_id": str(vert.id),
        "name": "Inter-College Football Championship 2026",
        "description": "Annual state tournament",
        "event_type": "TOURNAMENT",
        "planned_date": (date.today() + timedelta(days=30)).isoformat(),
        "location": "Main Stadium",
        "event_head_id": str(coordinator_user.id),
        "primary_poc_id": str(coordinator_user.id),
    }
    response = client.post("/api/v1/events", json=payload, headers=auth_headers_admin)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "PLANNING"
    assert data["event_head_username"] == coordinator_user.username
    event_id = data["id"]

    # Verify readiness checkpoints auto-created (8 items)
    r_resp = client.get(f"/api/v1/events/{event_id}/readiness", headers=auth_headers_admin)
    assert r_resp.status_code == status.HTTP_200_OK
    items = r_resp.json()
    assert len(items) == 8
    assert all(item["status"] == "NOT_STARTED" for item in items)


def test_event_lifecycle_transitions(
    client: TestClient,
    auth_headers_admin: dict,
    db_session: Session,
):
    """Verifies event lifecycle state transitions."""
    vert = db_session.scalar(select(Vertical).limit(1))
    from app.schemas.event import EventCreate
    from app.services.event_service import EventService
    service = EventService(db_session)
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    event = service.create_event(
        EventCreate(
            vertical_id=vert.id,
            name="Sprint Training Camp",
            planned_date=date.today() + timedelta(days=10),
            event_type=EventType.TRAINING,
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # 1. Transition to IN_PROGRESS
    resp1 = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "IN_PROGRESS", "remarks": "Camp commenced successfully"},
        headers=auth_headers_admin,
    )
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["status"] == "IN_PROGRESS"

    # 2. Transition to COMPLETED
    resp2 = client.post(
        f"/api/v1/events/{event.id}/transition",
        json={"status": "COMPLETED", "remarks": "All sessions completed"},
        headers=auth_headers_admin,
    )
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["status"] == "COMPLETED"


def test_event_team_management(
    client: TestClient,
    auth_headers_admin: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Verifies adding team members to an event."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    from app.schemas.event import EventCreate
    from app.services.event_service import EventService
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    event = EventService(db_session).create_event(
        EventCreate(
            vertical_id=vert.id,
            name="Team Management Cup",
            planned_date=date.today() + timedelta(days=15),
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # Add member
    add_resp = client.post(
        f"/api/v1/events/{event.id}/team",
        json={"user_id": str(coordinator_user.id), "role_in_event": "COORDINATOR", "notes": "Pitch manager"},
        headers=auth_headers_admin,
    )
    assert add_resp.status_code == status.HTTP_201_CREATED
    assert add_resp.json()["username"] == coordinator_user.username
    assert add_resp.json()["role_in_event"] == "COORDINATOR"


def test_event_readiness_update_and_dashboard(
    client: TestClient,
    auth_headers_admin: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Verifies updating readiness item and querying the aggregated operational dashboard."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    from app.schemas.event import EventCreate
    from app.services.event_service import EventService
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    event = EventService(db_session).create_event(
        EventCreate(
            vertical_id=vert.id,
            name="Dashboard Test Match",
            planned_date=date.today() + timedelta(days=5),
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # Get readiness items
    items = client.get(f"/api/v1/events/{event.id}/readiness", headers=auth_headers_admin).json()
    item_id = items[0]["id"]

    # Mark first item COMPLETED
    patch_resp = client.patch(
        f"/api/v1/events/{event.id}/readiness/{item_id}",
        json={"status": "COMPLETED", "evidence_link": "https://drive.google.com/doc1", "remarks": "Approved by Core"},
        headers=auth_headers_admin,
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["status"] == "COMPLETED"
    assert patch_resp.json()["completed_at"] is not None

    # Query operational dashboard
    dash_resp = client.get(f"/api/v1/events/{event.id}/dashboard", headers=auth_headers_admin)
    assert dash_resp.status_code == status.HTTP_200_OK
    dash = dash_resp.json()
    assert dash["event"]["name"] == "Dashboard Test Match"
    assert dash["readiness_summary"]["COMPLETED"] >= 1
    assert "tasks_count" in dash
    assert "requirements_count" in dash
