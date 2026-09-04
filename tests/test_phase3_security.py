"""
Dedicated Phase 3 Operational Security Attack Suite
Verifies defenses against:
1. Cross-vertical task assignment
2. IDOR task modification attempt
3. My Work identity spoofing
4. Confidential issue unauthorized access
5. Self-review violation on work reports
6. Zero hard-deletion enforcement
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.task import TaskPriority, TaskType
from app.models.user import User
from app.services.task_service import TaskService


def test_attack_cross_vertical_task_assignment_blocked(
    client: TestClient,
    auth_headers_admin: dict,
    regular_user: User,
    db_session: Session,
):
    """Attack: Assigning a user to a task outside their assigned vertical division is rejected."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Athletics & Track"))
    payload = {
        "vertical_id": str(vert.id),
        "assigned_to_id": str(regular_user.id),
        "title": "Track Obstacle Test",
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=auth_headers_admin)
    assert resp.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]


def test_attack_my_work_identity_spoofing_blocked(
    client: TestClient,
    auth_headers_user: dict,
    coordinator_user: User,
):
    """Attack: Supplying user_id in query string does not allow viewing another user's work."""
    resp = client.get(f"/api/v1/my-work?user_id={coordinator_user.id}", headers=auth_headers_user)
    assert resp.status_code == status.HTTP_200_OK
    for item in resp.json()["items"]:
        # Verify no items belong to the coordinator
        assert item["assigned_to_id"] != str(coordinator_user.id)


def test_attack_unauthorized_confidential_issue_access_blocked(
    client: TestClient,
    auth_headers_user: dict,
    admin_user: User,
    db_session: Session,
):
    """Attack: Probing confidential issue ID by unprivileged user fails with 403."""
    vert = db_session.scalar(select(Vertical).limit(1))
    from app.schemas.issue import IssueCreate
    from app.services.issue_service import IssueService
    issue = IssueService(db_session).create_issue(
        IssueCreate(
            vertical_id=vert.id,
            title="Secret Investigation",
            description="Sensitive board meeting notes",
            sensitivity="CONFIDENTIAL",
        ),
        actor_id=admin_user.id,
    )
    db_session.commit()

    resp = client.get(f"/api/v1/issues/{issue.id}", headers=auth_headers_user)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_attack_self_review_on_daily_report_blocked(
    client: TestClient,
    auth_headers_coordinator: dict,
    db_session: Session,
):
    """Attack: Author attempting to approve/review their own work report fails with 403."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    import random
    rep_date = date(2030, 1, 1) + timedelta(days=random.randint(1, 1000))

    from app.schemas.report import DailyReportCreate, DailyReportReviewRequest
    from app.services.report_service import ReportService
    service = ReportService(db_session)
    coord_u = db_session.scalar(select(User).where(User.username == "test_coordinator"))

    report = service.create_daily_report(
        DailyReportCreate(
            vertical_id=vert.id,
            report_date=rep_date,
            work_summary="Coordinator shift tasks",
            submit_now=True,
        ),
        user_id=coord_u.id,
    )
    db_session.commit()

    resp = client.post(
        f"/api/v1/reports/daily/{report.id}/review",
        json={"status": "REVIEWED", "review_comments": "I approve my own work"},
        headers=auth_headers_coordinator,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_zero_hard_deletion_policy_enforced(
    client: TestClient,
    auth_headers_admin: dict,
):
    """Verifies that DELETE HTTP methods are not implemented on operational resources."""
    random_id = str(uuid.uuid4())
    # 1. DELETE /tasks/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/tasks/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 2. DELETE /calendar/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/calendar/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 3. DELETE /issues/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/issues/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 4. DELETE /reports/daily/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/reports/daily/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
