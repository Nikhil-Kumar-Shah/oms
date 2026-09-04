"""
Organization & Verticals Test Suite
Hierarchy: Organization -> Vertical -> User (No Department concept)
"""

import uuid
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.organization import Vertical, VerticalStatus
from app.models.user import User
from app.services.organization_service import OrganizationService


def test_get_organization(client: TestClient, auth_headers_user: dict):
    """Verifies organization info and active verticals are returned."""
    response = client.get("/api/v1/organization", headers=auth_headers_user)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["code"] == "PARADOX_SPORTS"
    assert "verticals" in data
    assert len(data["verticals"]) >= 1


def test_list_verticals(client: TestClient, auth_headers_user: dict):
    """Verifies listing active verticals."""
    response = client.get("/api/v1/organization/verticals", headers=auth_headers_user)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    assert any(v["name"] == "Football Operations" for v in data["items"])


def test_create_vertical_by_admin(client: TestClient, auth_headers_admin: dict):
    """Verifies admin can create a new vertical division in PostgreSQL."""
    vert_name = f"Swimming Operations {uuid.uuid4().hex[:6]}"
    response = client.post(
        "/api/v1/admin/organization/verticals",
        json={"name": vert_name, "description": "Aquatic sports management"},
        headers=auth_headers_admin,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == vert_name
    assert data["status"] == "ACTIVE"


def test_cannot_assign_user_to_disabled_vertical(
    client: TestClient,
    auth_headers_admin: dict,
    regular_user: User,
    db_session: Session,
):
    """Verifies attempting to assign user to a DISABLED vertical fails with 422."""
    org_service = OrganizationService(db_session)
    # Create a disabled vertical
    vert = org_service.create_vertical(
        data=type("VerticalCreate", (), {"name": f"Disabled Vert {uuid.uuid4().hex[:6]}", "description": None, "organization_id": None})()
    )
    vert.status = VerticalStatus.DISABLED
    db_session.commit()

    payload = {
        "assignments": [
            {"vertical_id": str(vert.id), "is_primary": True}
        ]
    }
    response = client.post(
        f"/api/v1/admin/users/{regular_user.id}/verticals",
        json=payload,
        headers=auth_headers_admin,
    )
    assert response.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
