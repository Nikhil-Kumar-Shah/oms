"""
Master Calendar Test Suite
"""

from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.user import User


def test_create_calendar_entry(client: TestClient, auth_headers_admin: dict):
    """Verifies creating an organization-wide calendar entry."""
    payload = {
        "title": "Annual Sports Orientation Meeting",
        "description": "Introduction to athletic facilities and rules",
        "activity_date": (date.today() + timedelta(days=7)).isoformat(),
        "category": "ORIENTATION",
        "priority": "HIGH",
        "audience": "ORGANIZATION",
    }
    response = client.post("/api/v1/calendar", json=payload, headers=auth_headers_admin)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["category"] == "ORIENTATION"
    assert data["status"] == "PLANNED"


def test_calendar_audience_scoping(
    client: TestClient,
    auth_headers_coordinator: dict,
    auth_headers_user: dict,
    db_session: Session,
):
    """
    Verifies that a vertical-scoped calendar entry is visible only to users assigned
    to that vertical (or admins/sports core), and not to unassigned regular volunteers.
    """
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))

    from app.schemas.calendar import CalendarCreate
    from app.services.calendar_service import CalendarService
    service = CalendarService(db_session)

    entry = service.create_entry(
        CalendarCreate(
            title="Football Tactical Briefing",
            activity_date=date.today() + timedelta(days=3),
            category="REVIEW_MEETING",
            audience="VERTICAL",
            vertical_id=vert.id,
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # 1. Coordinator assigned to Football Operations CAN see the entry
    coord_resp = client.get("/api/v1/calendar", headers=auth_headers_coordinator)
    assert coord_resp.status_code == status.HTTP_200_OK
    coord_titles = [e["title"] for e in coord_resp.json()["items"]]
    assert "Football Tactical Briefing" in coord_titles

    # 2. Regular user NOT assigned to Football Operations CANNOT see the vertical-scoped entry
    user_resp = client.get("/api/v1/calendar", headers=auth_headers_user)
    assert user_resp.status_code == status.HTTP_200_OK
    user_titles = [e["title"] for e in user_resp.json()["items"]]
    assert "Football Tactical Briefing" not in user_titles
