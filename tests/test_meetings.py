"""
Operational Meetings & RSVPs Test Suite
"""

from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.user import User


def test_schedule_meeting_and_rsvp(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_coordinator: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Verifies creating a meeting, participant invitation, RSVP response, and rescheduling."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    m_date = date.today() + timedelta(days=4)

    payload = {
        "title": "Strategy & Fixture Discussion",
        "description": "Discussing league bracket matches",
        "meeting_type": "INTERNAL_SYNC",
        "meeting_date": m_date.isoformat(),
        "location": "Room 101",
        "vertical_id": str(vert.id),
        "participant_ids": [str(coordinator_user.id)],
    }
    resp = client.post("/api/v1/meetings", json=payload, headers=auth_headers_admin)
    assert resp.status_code == status.HTTP_201_CREATED
    meeting_id = resp.json()["id"]

    # Coordinator submits RSVP ACCEPTED
    rsvp_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/rsvp",
        json={"rsvp_status": "ACCEPTED", "notes": "Will attend in person"},
        headers=auth_headers_coordinator,
    )
    assert rsvp_resp.status_code == status.HTTP_200_OK
    assert rsvp_resp.json()["rsvp_status"] == "ACCEPTED"

    # Reschedule meeting
    new_date = date.today() + timedelta(days=6)
    resched_resp = client.post(
        f"/api/v1/meetings/{meeting_id}/reschedule",
        json={"meeting_date": new_date.isoformat(), "location": "Room 202", "remarks": "Pushed back 2 days"},
        headers=auth_headers_admin,
    )
    assert resched_resp.status_code == status.HTTP_200_OK
    assert resched_resp.json()["meeting_date"] == new_date.isoformat()
