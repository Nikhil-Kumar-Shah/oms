"""
Daily & Weekly Work Reports Test Suite
"""

import random
from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.user import User


def test_submit_daily_report_and_supervisor_review(
    client: TestClient,
    auth_headers_coordinator: dict,
    auth_headers_admin: dict,
    coordinator_user: User,
    db_session: Session,
):
    """
    Verifies daily work report submission by coordinator and supervisor review by admin.
    """
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    rep_date = date(2027, 1, 1) + timedelta(days=random.randint(1, 1000))

    # 1. Submit daily report
    payload = {
        "vertical_id": str(vert.id),
        "report_date": rep_date.isoformat(),
        "work_summary": "Completed turf inspection and cataloged football gear.",
        "tasks_completed": "2 routine inspections",
        "submit_now": True,
    }
    submit_resp = client.post("/api/v1/reports/daily", json=payload, headers=auth_headers_coordinator)
    assert submit_resp.status_code == status.HTTP_201_CREATED
    data = submit_resp.json()
    assert data["status"] == "SUBMITTED"
    report_id = data["id"]

    # 2. Supervisor (Admin) reviews and approves report
    review_payload = {
        "status": "REVIEWED",
        "review_comments": "Good work on the turf maintenance.",
    }
    rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json=review_payload,
        headers=auth_headers_admin,
    )
    assert rev_resp.status_code == status.HTTP_200_OK
    assert rev_resp.json()["status"] == "REVIEWED"
    assert rev_resp.json()["reviewed_at"] is not None


def test_duplicate_daily_report_rejected(
    client: TestClient,
    auth_headers_coordinator: dict,
    db_session: Session,
):
    """Verifies that submitting a second report for the same user and date is rejected."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    rep_date = date(2028, 1, 1) + timedelta(days=random.randint(1, 1000))

    payload = {
        "vertical_id": str(vert.id),
        "report_date": rep_date.isoformat(),
        "work_summary": "First submission for test date.",
    }
    # First submission -> 201
    resp1 = client.post("/api/v1/reports/daily", json=payload, headers=auth_headers_coordinator)
    assert resp1.status_code == status.HTTP_201_CREATED

    # Second submission for same date -> 422
    resp2 = client.post("/api/v1/reports/daily", json=payload, headers=auth_headers_coordinator)
    assert resp2.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]


def test_self_review_prevention_on_daily_report(
    client: TestClient,
    auth_headers_coordinator: dict,
    db_session: Session,
):
    """
    Verifies that an author CANNOT review their own report (Self-Review Prohibition).
    """
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    rep_date = date(2030, 1, 1) + timedelta(days=random.randint(1, 50000))

    # 1. Submit report as coordinator
    payload = {
        "vertical_id": str(vert.id),
        "report_date": rep_date.isoformat(),
        "work_summary": "Shift summary by coordinator.",
        "submit_now": True,
    }
    submit_resp = client.post("/api/v1/reports/daily", json=payload, headers=auth_headers_coordinator)
    assert submit_resp.status_code == status.HTTP_201_CREATED
    report_id = submit_resp.json()["id"]

    # 2. Coordinator attempts to approve their OWN report -> 403 Forbidden
    self_rev_resp = client.post(
        f"/api/v1/reports/daily/{report_id}/review",
        json={"status": "REVIEWED", "review_comments": "Self approving my own report"},
        headers=auth_headers_coordinator,
    )
    assert self_rev_resp.status_code == status.HTTP_403_FORBIDDEN
