"""
Backend Security Boundary Tests
Verifies the hardened API access classification:
- DISABLED: /dev, /dev/* (404)
- PUBLIC: / (minimal metadata), /health (minimal safe probe), POST /api/v1/auth/login
- HIGHLY RESTRICTED: /docs, /redoc, /openapi.json (HTTP Basic Auth)
- AUTHENTICATED: GET /api/v1 (discovery), /api/v1/* (operational routes)
"""

import time
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import get_settings

settings = get_settings()


# -----------------------------------------------------------------------------
# 1. Disabled Development Surface (/dev)
# -----------------------------------------------------------------------------

def test_dev_routes_are_completely_disabled(client: TestClient):
    """Verifies that /dev and all nested /dev/* routes return 404 Not Found."""
    assert client.get("/dev").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/dev/").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/dev/tasks").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/dev/auth/login").status_code == status.HTTP_404_NOT_FOUND
    assert client.post("/dev/tasks/create", data={}).status_code == status.HTTP_404_NOT_FOUND


# -----------------------------------------------------------------------------
# 2. Public Boundary: Root (/) & Minimal Health (/health)
# -----------------------------------------------------------------------------

def test_root_endpoint_returns_minimal_metadata_and_no_redirect(client: TestClient):
    """Verifies GET / returns minimal service discovery JSON without redirecting to /dev."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["status"] == "online"
    # Ensure no internal paths/secrets
    assert "password" not in response.text.lower()
    assert "postgresql" not in response.text.lower()


def test_public_health_endpoint_returns_safe_status(client: TestClient):
    """Verifies GET /health returns safe status without exposing database connection strings or internals."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == {"status": "healthy"}
    assert "password" not in response.text.lower()
    assert "postgresql" not in response.text.lower()
    assert "traceback" not in response.text.lower()


# -----------------------------------------------------------------------------
# 3. Restricted Documentation Boundary (/docs, /redoc, /openapi.json)
# -----------------------------------------------------------------------------

def test_docs_endpoints_require_basic_authentication(client: TestClient):
    """Verifies /docs, /redoc, and /openapi.json reject unauthenticated and invalid requests."""
    # 1. Unauthenticated -> 401 with WWW-Authenticate header
    for path in ["/docs", "/redoc", "/openapi.json"]:
        resp = client.get(path)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "www-authenticate" in resp.headers
        assert "basic" in resp.headers["www-authenticate"].lower()

    # 2. Invalid Credentials -> 401
    bad_auth = ("wrong_user", "wrong_password")
    for path in ["/docs", "/redoc", "/openapi.json"]:
        resp = client.get(path, auth=bad_auth)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Valid Credentials -> 200 OK
    good_auth = (settings.API_DOCS_USERNAME, settings.API_DOCS_PASSWORD)

    docs_resp = client.get("/docs", auth=good_auth)
    assert docs_resp.status_code == status.HTTP_200_OK
    assert "swagger-ui" in docs_resp.text.lower()

    redoc_resp = client.get("/redoc", auth=good_auth)
    assert redoc_resp.status_code == status.HTTP_200_OK
    assert "redoc" in redoc_resp.text.lower()

    openapi_resp = client.get("/openapi.json", auth=good_auth)
    assert openapi_resp.status_code == status.HTTP_200_OK
    schema = openapi_resp.json()
    assert "paths" in schema
    assert len(schema["paths"]) >= 120


# -----------------------------------------------------------------------------
# 4. Authenticated API Boundary (GET /api/v1 and /api/v1/*)
# -----------------------------------------------------------------------------

def test_api_v1_discovery_requires_authentication(client: TestClient, auth_headers_admin: dict):
    """Verifies GET /api/v1 rejects unauthenticated callers and responds to authenticated users."""
    # Unauthenticated -> 401
    unauth_resp = client.get("/api/v1")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Authenticated -> 200
    auth_resp = client.get("/api/v1", headers=auth_headers_admin)
    assert auth_resp.status_code == status.HTTP_200_OK
    data = auth_resp.json()
    assert data["version"] == "v1"
    assert len(data["resource_groups"]) >= 20


def test_auth_login_remains_publicly_accessible(client: TestClient):
    """Verifies POST /api/v1/auth/login is accessible without existing session."""
    # Valid credentials -> 200
    valid_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPassword@123"})
    assert valid_resp.status_code == status.HTTP_200_OK
    assert "session" in valid_resp.json()

    # Invalid credentials -> 401
    invalid_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert invalid_resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_routes_require_authentication_and_rbac(
    client: TestClient,
    auth_headers_user: dict,
    auth_headers_admin: dict,
):
    """Verifies authenticated role enforcement across /api/v1 routes."""
    # Unauthenticated -> 401
    assert client.get("/api/v1/tasks").status_code == status.HTTP_401_UNAUTHORIZED
    assert client.get("/api/v1/admin/users").status_code == status.HTTP_401_UNAUTHORIZED

    # Volunteer User -> 403 Forbidden on Admin routes
    assert client.get("/api/v1/admin/users", headers=auth_headers_user).status_code == status.HTTP_403_FORBIDDEN

    # Admin User -> 200 OK on Admin routes
    assert client.get("/api/v1/admin/users", headers=auth_headers_admin).status_code == status.HTTP_200_OK


# -----------------------------------------------------------------------------
# 5. Latency & Performance Verification of Security Boundary
# -----------------------------------------------------------------------------

def test_security_boundary_performance_latencies(client: TestClient, auth_headers_admin: dict):
    """Verifies security middleware adds negligible overhead to requests."""
    # Warmup request
    client.get("/health")

    # 1. Public Health (< 50ms)
    t0 = time.perf_counter()
    resp_health = client.get("/health")
    lat_health = (time.perf_counter() - t0) * 1000
    assert resp_health.status_code == 200
    assert lat_health < 50.0

    # 2. Basic Auth Docs (< 100ms)
    t0 = time.perf_counter()
    resp_docs = client.get("/docs", auth=(settings.API_DOCS_USERNAME, settings.API_DOCS_PASSWORD))
    lat_docs = (time.perf_counter() - t0) * 1000
    assert resp_docs.status_code == 200
    assert lat_docs < 100.0

    # 3. Authenticated API Discovery (< 100ms)
    t0 = time.perf_counter()
    resp_api = client.get("/api/v1", headers=auth_headers_admin)
    lat_api = (time.perf_counter() - t0) * 1000
    assert resp_api.status_code == 200
    assert lat_api < 100.0
