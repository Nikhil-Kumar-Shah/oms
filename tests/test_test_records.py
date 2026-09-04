"""
Tests for SystemTestRecord CRUD & Validation
"""

import uuid
from fastapi import status
from fastapi.testclient import TestClient


def test_create_test_record_success(client: TestClient):
    """Verifies creating a SystemTestRecord returns 201 Created and persists UUID & timestamps."""
    payload = {
        "name": "Unit Test Record Alpha",
        "description": "Created during automated pytest execution",
    }
    response = client.post("/api/v1/test-records", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify ID is a valid UUID
    record_id = data["id"]
    uuid.UUID(record_id)

    # Immediately fetch record by ID
    get_resp = client.get(f"/api/v1/test-records/{record_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    fetched = get_resp.json()
    assert fetched["id"] == record_id
    assert fetched["name"] == payload["name"]


def test_list_test_records(client: TestClient):
    """Verifies listing records returns paginated response."""
    response = client.get("/api/v1/test-records")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


def test_get_nonexistent_record_returns_404(client: TestClient):
    """Verifies querying a non-existent UUID returns 404 EntityNotFound."""
    random_uuid = str(uuid.uuid4())
    response = client.get(f"/api/v1/test-records/{random_uuid}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ENTITY_NOT_FOUND"


def test_create_record_validation_failure_empty_name(client: TestClient):
    """Verifies submitting empty name returns 422 Unprocessable Entity."""
    payload = {"name": "", "description": "Invalid empty name"}
    response = client.post("/api/v1/test-records", json=payload)
    assert response.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_persistence_across_fresh_client_requests(client: TestClient):
    """
    Verifies data is truly stored in PostgreSQL and accessible across independent client requests.
    """
    test_name = f"Persistence-Test-{uuid.uuid4().hex[:8]}"
    create_resp = client.post(
        "/api/v1/test-records",
        json={"name": test_name, "description": "Checking persistence across fresh calls"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    record_id = create_resp.json()["id"]

    # Retrieve in second request
    fetch_resp = client.get(f"/api/v1/test-records/{record_id}")
    assert fetch_resp.status_code == status.HTTP_200_OK
    assert fetch_resp.json()["name"] == test_name
