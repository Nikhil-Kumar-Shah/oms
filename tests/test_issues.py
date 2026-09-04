"""
Issue & Escalation Register Test Suite
"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.user import User


def test_raise_issue_and_escalate(
    client: TestClient,
    auth_headers_admin: dict,
    db_session: Session,
):
    """Verifies raising an issue, escalating it, and resolving it."""
    vert = db_session.scalar(select(Vertical).limit(1))

    # 1. Raise Issue
    payload = {
        "vertical_id": str(vert.id),
        "title": "Broken hydraulic jack in gym",
        "description": "Equipment failure during morning warm-up session",
        "sensitivity": "NORMAL",
        "action_required": "Replace hydraulic seal",
    }
    raise_resp = client.post("/api/v1/issues", json=payload, headers=auth_headers_admin)
    assert raise_resp.status_code == status.HTTP_201_CREATED
    issue_id = raise_resp.json()["id"]

    # 2. Escalate Issue
    esc_resp = client.post(
        f"/api/v1/issues/{issue_id}/escalate",
        json={
            "escalation_target": "Head of Equipment Logistics",
            "escalation_action": "Order replacement parts immediately",
        },
        headers=auth_headers_admin,
    )
    assert esc_resp.status_code == status.HTTP_200_OK
    assert esc_resp.json()["status"] == "ESCALATED"
    assert esc_resp.json()["escalation_target"] == "Head of Equipment Logistics"

    # 3. Resolve Issue
    res_resp = client.post(
        f"/api/v1/issues/{issue_id}/transition",
        json={"status": "RESOLVED", "resolution": "Part replaced and certified safe."},
        headers=auth_headers_admin,
    )
    assert res_resp.status_code == status.HTTP_200_OK
    assert res_resp.json()["status"] == "RESOLVED"
    assert res_resp.json()["resolution"] == "Part replaced and certified safe."
    assert res_resp.json()["resolution_date"] is not None


def test_confidential_issue_access_protection(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_user: dict,
    db_session: Session,
):
    """
    Verifies that CONFIDENTIAL issues cannot be accessed by unauthorized users
    merely by guessing or probing the issue ID (IDOR protection).
    """
    vert = db_session.scalar(select(Vertical).limit(1))
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    from app.schemas.issue import IssueCreate
    from app.services.issue_service import IssueService
    service = IssueService(db_session)

    issue = service.create_issue(
        IssueCreate(
            vertical_id=vert.id,
            title="Confidential Disciplinary Matter",
            description="Private investigation regarding code of conduct violation",
            sensitivity="CONFIDENTIAL",
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # 1. Admin CAN access the confidential issue
    admin_resp = client.get(f"/api/v1/issues/{issue.id}", headers=auth_headers_admin)
    assert admin_resp.status_code == status.HTTP_200_OK

    # 2. Unauthorized volunteer CANNOT access the confidential issue (403 Forbidden)
    user_resp = client.get(f"/api/v1/issues/{issue.id}", headers=auth_headers_user)
    assert user_resp.status_code == status.HTTP_403_FORBIDDEN
