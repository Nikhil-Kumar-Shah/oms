"""
Tests for Health Verification Endpoints
"""

from fastapi import status
from fastapi.testclient import TestClient


def test_app_health_endpoint(client: TestClient):
    """Verifies GET /api/v1/health returns 200 OK with valid application metadata."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data
    assert "timestamp" in data
    assert "environment" in data


def test_database_health_endpoint(client: TestClient):
    """Verifies GET /api/v1/health/database performs live query and returns latency."""
    response = client.get("/api/v1/health/database")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert isinstance(data["latency_ms"], (int, float))
    assert data["latency_ms"] >= 0


def test_request_correlation_header(client: TestClient):
    """Verifies X-Request-ID and X-Process-Time-Ms headers are injected into HTTP responses."""
    custom_id = "test-correlation-id-12345"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("X-Request-ID") == custom_id
    assert "X-Process-Time-Ms" in response.headers
