"""
Cross-Vertical Requirements Test Suite
"""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.user import User


def test_create_and_transition_requirement(
    client: TestClient,
    auth_headers_admin: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Verifies creating a cross-vertical requirement, assigning, and transitioning status."""
    v_source = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    v_target = db_session.scalar(select(Vertical).where(Vertical.name == "Logistics & Equipment"))

    payload = {
        "title": "Supply 10 Match Quality Footballs",
        "description": "Required for upcoming fixture on pitch 2",
        "requesting_vertical_id": str(v_source.id),
        "target_vertical_id": str(v_target.id),
        "priority": "HIGH",
    }
    resp = client.post("/api/v1/requirements", json=payload, headers=auth_headers_admin)
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["status"] == "OPEN"
    req_id = data["id"]

    # Transition to IN_PROGRESS
    trans_resp = client.post(
        f"/api/v1/requirements/{req_id}/transition",
        json={"status": "IN_PROGRESS", "remarks": "Footballs allocated from warehouse"},
        headers=auth_headers_admin,
    )
    assert trans_resp.status_code == status.HTTP_200_OK
    assert trans_resp.json()["status"] == "IN_PROGRESS"

    # Post message
    msg_resp = client.post(
        f"/api/v1/requirements/{req_id}/messages",
        json={"content": "Footballs have arrived at the changing room."},
        headers=auth_headers_admin,
    )
    assert msg_resp.status_code == status.HTTP_201_CREATED
    assert msg_resp.json()["content"] == "Footballs have arrived at the changing room."

    # List messages
    msgs_resp = client.get(f"/api/v1/requirements/{req_id}/messages", headers=auth_headers_admin)
    assert msgs_resp.status_code == status.HTTP_200_OK
    assert len(msgs_resp.json()) >= 1
