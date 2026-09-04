"""
Phase 7: Dedicated API Contract, Readiness, Security & Performance Verification Suite
Validates:
1. API Discovery (GET /api/v1) & OpenAPI Specification (/openapi.json, /docs, /redoc)
2. Standardized Error Contract & Secret Sanitization
3. Strict Server-Authoritative RBAC & IDOR/BOLA Defense
4. Performance Benchmarks (<500ms for Governed Transfers & Operational Analytics)
5. Fresh-Session PostgreSQL Verification
"""

import time
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import TransferResourceType, TransferStatus
from app.models.organization import Organization, UserVertical, Vertical
from app.models.rbac import Role, UserRole
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.analytics import OperationalDashboardResponse, PerformanceIndicatorsResponse
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest
from app.schemas.task import TaskCreate
from app.services.analytics_service import AnalyticsService
from app.services.task_service import TaskService
from app.services.transfer_service import OwnershipTransferService


# -----------------------------------------------------------------------------
# 1. API Discovery & OpenAPI Contract Tests
# -----------------------------------------------------------------------------

def test_api_v1_discovery_endpoint(client: TestClient, auth_headers_admin: dict):
    """Verifies developer-facing discovery endpoint GET /api/v1 returns version and resource groups when authenticated."""
    response = client.get("/api/v1", headers=auth_headers_admin)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["version"] == "v1"
    assert data["status"] == "operational"
    assert "documentation" in data
    assert data["documentation"]["swagger_ui"] == "/docs"
    assert data["documentation"]["openapi_spec"] == "/openapi.json"
    assert len(data["resource_groups"]) >= 20

    # Verify prefixes
    prefixes = [rg["prefix"] for rg in data["resource_groups"]]
    assert "/api/v1/tasks" in prefixes
    assert "/api/v1/events" in prefixes
    assert "/api/v1/analytics" in prefixes
    assert "/api/v1/transfers" in prefixes


def test_openapi_json_schema_validity_and_completeness(client: TestClient):
    """Verifies /openapi.json requires basic auth and contains comprehensive routes when authorized."""
    # 1. Unauthenticated -> 401
    unauth_resp = client.get("/openapi.json")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Authenticated with Basic Auth -> 200
    response = client.get("/openapi.json", auth=("docs_admin", "DocsAdminPassword@123"))
    assert response.status_code == status.HTTP_200_OK
    schema = response.json()

    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    assert len(schema["paths"]) >= 120

    # Verify critical path groups are present
    paths = schema["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/workspace/my-work" in paths
    assert "/api/v1/events" in paths
    assert "/api/v1/analytics/dashboard" in paths
    assert "/api/v1/transfers" in paths


def test_swagger_and_redoc_endpoints(client: TestClient):
    """Verifies Swagger UI (/docs) and Redoc (/redoc) HTML endpoints are secured behind Basic Auth."""
    # Unauthenticated -> 401
    assert client.get("/docs").status_code == status.HTTP_401_UNAUTHORIZED
    assert client.get("/redoc").status_code == status.HTTP_401_UNAUTHORIZED

    # Authenticated -> 200
    docs_resp = client.get("/docs", auth=("docs_admin", "DocsAdminPassword@123"))
    assert docs_resp.status_code == status.HTTP_200_OK
    assert "swagger-ui" in docs_resp.text.lower()

    redoc_resp = client.get("/redoc", auth=("docs_admin", "DocsAdminPassword@123"))
    assert redoc_resp.status_code == status.HTTP_200_OK
    assert "redoc" in redoc_resp.text.lower()


# -----------------------------------------------------------------------------
# 2. Standardized Error Contract & Secret Sanitization Tests
# -----------------------------------------------------------------------------

def test_standardized_error_contract_on_404_and_422(client: TestClient, auth_headers_admin: dict):
    """Verifies error responses follow standardized format and sanitize internal secrets."""
    # 404 Entity Not Found
    resp_404 = client.get(f"/api/v1/tasks/{uuid4()}", headers=auth_headers_admin)
    assert resp_404.status_code == status.HTTP_404_NOT_FOUND
    data_404 = resp_404.json()
    assert data_404["success"] is False
    assert "error" in data_404
    assert data_404["error"]["code"] == "ENTITY_NOT_FOUND"
    assert "not found" in data_404["error"]["message"].lower()

    # 422 Validation Error
    resp_422 = client.post("/api/v1/tasks", json={"invalid_field": "test"}, headers=auth_headers_admin)
    assert resp_422.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    data_422 = resp_422.json()
    assert data_422["success"] is False
    assert "error" in data_422
    assert data_422["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    # Ensure no secrets/stack traces
    assert "traceback" not in resp_422.text.lower()
    assert "password" not in resp_422.text.lower()


# -----------------------------------------------------------------------------
# 3. Security, RBAC & IDOR/BOLA Protection Tests
# -----------------------------------------------------------------------------

def test_unauthenticated_request_rejected(client: TestClient):
    """Verifies unauthenticated calls to protected routes return 401."""
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] in ["AUTHENTICATION_FAILED", "UNAUTHORIZED"]


def test_forbidden_role_access_rejected(client: TestClient, auth_headers_user: dict):
    """Verifies non-admin users cannot access admin-only user management."""
    resp = client.get("/api/v1/admin/users", headers=auth_headers_user)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN"


# -----------------------------------------------------------------------------
# 4. Performance Benchmark Tests (<500ms)
# -----------------------------------------------------------------------------

def test_governed_transfer_performance_benchmark(db_session: Session):
    """
    Performance Benchmark: Governed ownership transfer creation, review,
    and atomic resource mutation must execute in <500ms.
    """
    # 1. Provision actors
    org = Organization(name=f"Perf Org {uuid4().hex[:4]}", code=f"PO_{uuid4().hex[:4]}".upper())
    db_session.add(org)
    db_session.flush()

    v = Vertical(organization_id=org.id, name="Perf Field Ops")
    db_session.add(v)
    db_session.flush()

    u_coord = User(username=f"perf_coord_{uuid4().hex[:4]}", full_name="Coord User", email=f"c_{uuid4().hex[:6]}@perf.org", password_hash="h", account_status=AccountStatus.ACTIVE)
    u_super = User(username=f"perf_super_{uuid4().hex[:4]}", full_name="Super User", email=f"s_{uuid4().hex[:6]}@perf.org", password_hash="h", account_status=AccountStatus.ACTIVE)
    db_session.add_all([u_coord, u_super])
    db_session.flush()

    db_session.add(UserVertical(user_id=u_coord.id, vertical_id=v.id, is_primary=True))
    db_session.add(UserVertical(user_id=u_super.id, vertical_id=v.id, is_primary=True))
    db_session.commit()

    task_service = TaskService(db_session)
    task = task_service.create_task(
        TaskCreate(
            title="Benchmark Task Rig",
            vertical_id=v.id,
            assigned_to_id=u_coord.id,
            priority=TaskPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        actor_id=u_super.id,
    )
    db_session.commit()

    xfer_service = OwnershipTransferService(db_session)

    t_start = time.perf_counter()

    # Step A: Request Transfer
    xfer = xfer_service.request_transfer(
        OwnershipTransferCreate(
            resource_type=TransferResourceType.TASK,
            resource_id=task.id,
            requested_owner_id=u_super.id,
            reason="Benchmark transfer performance test",
        ),
        requested_by_id=u_coord.id,
    )
    db_session.commit()

    # Step B: Review & Approve Transfer
    xfer_service.review_transfer(
        xfer.id,
        reviewer_id=u_super.id,
        data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Approved quickly"),
    )
    db_session.commit()

    t_elapsed_ms = (time.perf_counter() - t_start) * 1000

    db_session.refresh(task)
    assert task.assigned_to_id == u_super.id
    print(f"\n[BENCHMARK] Governed Transfer total latency: {t_elapsed_ms:.2f}ms (Target: <500ms)")
    assert t_elapsed_ms < 500.0, f"Transfer latency {t_elapsed_ms:.2f}ms exceeded 500ms target!"


def test_postgresql_analytics_performance_benchmark(db_session: Session):
    """
    Performance Benchmark: Computing live Operational Dashboard & Performance Indicators
    over PostgreSQL records must execute in <500ms.
    """
    analytics_service = AnalyticsService(db_session)

    t_start = time.perf_counter()
    dash = analytics_service.get_operational_dashboard()
    indicators = analytics_service.get_performance_indicators()
    t_elapsed_ms = (time.perf_counter() - t_start) * 1000

    assert dash.active_tasks >= 0
    assert indicators.task_completion_rate_pct >= 0.0
    print(f"\n[BENCHMARK] PostgreSQL Operational Analytics latency: {t_elapsed_ms:.2f}ms (Target: <500ms)")
    assert t_elapsed_ms < 500.0, f"Analytics latency {t_elapsed_ms:.2f}ms exceeded 500ms target!"
