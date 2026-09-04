"""
Advanced Forms & Structured Submissions Test Suite
"""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Vertical
from app.models.task import Task
from app.models.user import User


def test_form_lifecycle_validation_and_transformation(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_coordinator: dict,
    coordinator_user: User,
    admin_user: User,
    db_session: Session,
):
    """
    Verifies:
    1. Creating form with schema & transformation config
    2. Publishing version 1 (making it immutable)
    3. Schema validation rejection on invalid submission
    4. Successful submission by coordinator
    5. Self-approval blocked (coordinator cannot approve own submission)
    6. Admin approves submission -> Triggers Transactional Transformation to Master Task!
    """
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))

    # 1. Create Form
    payload = {
        "name": "Pitch Equipment Work Request",
        "purpose": "Procurement and setup of pitch materials",
        "vertical_id": str(vert.id),
        "target_audience": "ORGANIZATION",
        "initial_schema": [
            {"key": "title", "label": "Task Summary", "type": "TEXT", "required": True},
            {"key": "quantity", "label": "Quantity Needed", "type": "NUMBER", "required": True, "validation_rules": {"min_value": 1, "max_value": 100}},
            {"key": "details", "label": "Specific Notes", "type": "LONG_TEXT", "required": False},
        ],
        "transformation_config": {
            "target_entity": "TASK",
            "field_mappings": {"title": "title", "description": "details"},
        },
    }
    form_resp = client.post("/api/v1/forms", json=payload, headers=auth_headers_admin)
    assert form_resp.status_code == status.HTTP_201_CREATED
    form_id = form_resp.json()["id"]

    # 2. Publish Version 1
    pub_resp = client.post(f"/api/v1/forms/{form_id}/publish?version_number=1", headers=auth_headers_admin)
    assert pub_resp.status_code == status.HTTP_200_OK
    assert pub_resp.json()["is_published"] is True

    # 3. Schema validation failure (missing required title & invalid quantity)
    invalid_sub = {"submission_data": {"quantity": 500}}  # Exceeds max_value 100 and missing required title
    inv_resp = client.post(f"/api/v1/forms/{form_id}/submissions", json=invalid_sub, headers=auth_headers_coordinator)
    assert inv_resp.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]

    # 4. Valid submission by coordinator
    valid_sub = {"submission_data": {"title": "Procure 24 Training Cones", "quantity": 24, "details": "Orange high-visibility cones for evening drill"}}
    sub_resp = client.post(f"/api/v1/forms/{form_id}/submissions", json=valid_sub, headers=auth_headers_coordinator)
    assert sub_resp.status_code == status.HTTP_201_CREATED
    sub_data = sub_resp.json()
    assert sub_data["status"] == "SUBMITTED"
    submission_id = sub_data["id"]

    # 5. Coordinator attempts self-approval -> 403 Forbidden
    self_app_resp = client.post(
        f"/api/v1/form-submissions/{submission_id}/review",
        json={"status": "APPROVED", "review_comments": "Self approval"},
        headers=auth_headers_coordinator,
    )
    assert self_app_resp.status_code == status.HTTP_403_FORBIDDEN

    # 6. Admin approves -> Transforms into Master Task
    rev_resp = client.post(
        f"/api/v1/form-submissions/{submission_id}/review",
        json={"status": "APPROVED", "review_comments": "Approved for purchase", "execute_transformation": True},
        headers=auth_headers_admin,
    )
    assert rev_resp.status_code == status.HTTP_200_OK
    res_data = rev_resp.json()
    assert res_data["status"] == "APPROVED"
    assert res_data["transformed_entity_type"] == "TASK"
    task_id = res_data["transformed_entity_id"]
    assert task_id is not None

    # Verify task exists in PostgreSQL
    created_task = db_session.get(Task, task_id)
    assert created_task is not None
    assert created_task.title == "Procure 24 Training Cones"
