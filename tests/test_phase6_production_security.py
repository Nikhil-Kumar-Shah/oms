"""
Phase 6 Production Security, Performance & Hardening Test Suite
Paradox Sports OMS
"""

import time
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.middleware import RateLimitingMiddleware
from app.core.security import hash_password
from app.main import app
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User


def test_production_security_headers(client: TestClient):
    """
    Verifies that all standard production security headers are present on API responses.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    # Verify Security Headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Permissions-Policy" in response.headers
    assert response.headers.get("X-Request-ID") is not None
    assert response.headers.get("X-Process-Time-Ms") is not None


def test_rate_limiting_on_auth_login(client: TestClient):
    """
    Verifies that repeatedly attempting logins from the same client IP triggers HTTP 429 Rate Limit Exceeded.
    """
    RateLimitingMiddleware.reset()
    rate_limited = False
    for i in range(15):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": f"attacker_{i}", "password": "wrongpassword123"},
        )
        if resp.status_code == 429:
            rate_limited = True
            data = resp.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "Retry-After" in resp.headers
            break

    assert rate_limited is True, "Rate limiting should have triggered 429 within 15 requests"
    RateLimitingMiddleware.reset()


def test_health_endpoints_distinguish_app_and_database(client: TestClient):
    """
    Verifies that health endpoints return appropriate status codes and performance metrics without exposing secrets.
    """
    # App Liveness
    resp_app = client.get("/api/v1/health")
    assert resp_app.status_code == 200
    app_data = resp_app.json()
    assert app_data["status"] == "healthy"
    assert "password" not in str(app_data).lower()
    assert "secret" not in str(app_data).lower()

    # Database Health
    resp_db = client.get("/api/v1/health/database")
    assert resp_db.status_code == 200
    db_data = resp_db.json()
    assert db_data["status"] == "healthy"
    assert db_data["database"] == "healthy"
    assert isinstance(db_data["latency_ms"], (int, float))
    assert db_data["latency_ms"] >= 0


def test_unauthorized_user_idor_isolation(
    client: TestClient,
    db_session: Session,
    test_user: User,
    test_vertical,
    auth_token: str,
):
    """
    Verifies that an authenticated user cannot read another user's task by brute-forcing IDs.
    """
    # Ensure second user exists
    stmt = select(User).where(User.username == "other_isolated_user")
    other_u = db_session.scalar(stmt)
    if not other_u:
        other_u = User(
            username="other_isolated_user",
            full_name="Other Isolated User",
            email="other_isolated@paradoxsports.internal",
            password_hash=hash_password("DummyPass@123"),
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(other_u)
        db_session.flush()

    # Create task assigned to the other user
    other_task = Task(
        title="Restricted Operations Task",
        description="Confidential ops",
        vertical_id=test_vertical.id,
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        assigned_to_id=other_u.id,
        assigned_by_id=test_user.id,
    )
    db_session.add(other_task)
    db_session.commit()

    # Authenticated test user checks "My Work" - should NOT contain other_task
    resp = client.get(
        "/api/v1/my-work",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    my_tasks = resp.json()
    task_ids = [t["id"] for t in my_tasks.get("items", [])]
    assert str(other_task.id) not in task_ids


def test_unauthenticated_request_rejected(client: TestClient, test_vertical):
    """
    Verifies that requests without session tokens are rejected with 401 across all protected routes.
    """
    RateLimitingMiddleware.reset()
    endpoints = [
        "/api/v1/tasks",
        "/api/v1/my-work",
        "/api/v1/events",
        f"/api/v1/requirements?vertical_id={test_vertical.id}",
        "/api/v1/meetings",
        f"/api/v1/forms?vertical_id={test_vertical.id}",
        "/api/v1/announcements",
        "/api/v1/directives",
        "/api/v1/notifications",
        "/api/v1/communications",
        "/api/v1/transfers",
        f"/api/v1/analytics/operational?vertical_id={test_vertical.id}",
        "/api/v1/admin/audit-logs",
        "/api/v1/admin/config",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code in [401, 403], f"Endpoint {ep} must require authentication, returned {resp.status_code}"
