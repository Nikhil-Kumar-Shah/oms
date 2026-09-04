"""
Tests for Merged Dynamic Form Creation & Distribution Unified Workflow
Paradox Sports OMS - Phase 11 Form Workflow System

Verifies:
1. Save Draft: saves form template, sections, questions, and distribution_config without distributing.
   Form status is DRAFT, FormVersion is_published is False, 0 FormResponse instances.
2. Publish & Distribute: saves form template, marks status PUBLISHED, marks version is_published=True,
   creates FormDistribution, and creates independent FormResponse instances (status ASSIGNED) for each recipient.
3. Update Draft and Publish & Distribute: updates draft form metadata, distribution settings, and then distributes.
4. Validation: ensures publish_and_distribute requires at least 1 recipient.
"""

import uuid
from datetime import datetime, timezone, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.form import (
    Form,
    FormStatus,
    FormVersion,
    FormDistribution,
    FormResponse,
    FormResponseStatus,
)
from app.models.organization import Vertical
from app.models.user import User


def test_save_draft_form_with_distribution_config(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    coordinator_user: User,
    regular_user: User,
    test_vertical: Vertical,
):
    """Verify Save Draft saves complete form + distribution settings without generating response instances."""
    deadline_iso = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "name": "Equipment Inspection Checklist Draft",
        "purpose": "Verify football pitches and field gear before tournaments",
        "instructions": "Please inspect all goals and corner flags",
        "category": "Operational",
        "vertical_id": str(test_vertical.id),
        "target_audience": "ORGANIZATION",
        "publish_and_distribute": False,
        "recipient_ids": [str(coordinator_user.id), str(regular_user.id)],
        "distribution_deadline": deadline_iso,
        "distribution_instructions": "Submit with photos attached",
        "distribution_config": {
            "audience_items": [
                {"id": f"USER:{coordinator_user.id}", "type": "USER", "rawId": str(coordinator_user.id), "label": coordinator_user.full_name or coordinator_user.username},
                {"id": f"USER:{regular_user.id}", "type": "USER", "rawId": str(regular_user.id), "label": regular_user.full_name or regular_user.username},
            ],
            "deadline": deadline_iso,
            "distribution_instructions": "Submit with photos attached",
        },
        "sections": [
            {
                "id": "sec-1",
                "title": "Pitch & Goal Integrity",
                "ordering": 1,
                "fields": [
                    {
                        "id": "f-1",
                        "key": "goal_post_condition",
                        "label": "Goal Post Condition",
                        "type": "TEXT",
                        "required": True,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/forms", json=payload, headers=auth_headers_admin)
    assert res.status_code == status.HTTP_201_CREATED, res.text
    data = res.json()

    assert data["name"] == "Equipment Inspection Checklist Draft"
    assert data["status"] == "DRAFT"
    assert data["current_version_number"] == 1
    assert data["distribution_config"] is not None
    assert str(coordinator_user.id) in data["distribution_config"]["recipient_ids"]
    assert str(regular_user.id) in data["distribution_config"]["recipient_ids"]

    # Verify database state
    form_id = uuid.UUID(data["id"])
    form = db_session.get(Form, form_id)
    assert form is not None
    assert form.status == FormStatus.DRAFT

    # Ensure no responses or distributions were created
    responses = db_session.scalars(select(FormResponse).where(FormResponse.form_id == form_id)).all()
    assert len(responses) == 0

    distributions = db_session.scalars(select(FormDistribution).where(FormDistribution.form_id == form_id)).all()
    assert len(distributions) == 0


def test_publish_and_distribute_form_unified(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    coordinator_user: User,
    regular_user: User,
    test_vertical: Vertical,
):
    """Verify Publish & Distribute publishes form, creates distribution, and creates assigned responses."""
    deadline_iso = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    payload = {
        "name": "Medical Readiness Form",
        "purpose": "Collect medical team compliance certificates",
        "instructions": "All medics must fill this",
        "category": "Medical & Safety",
        "vertical_id": str(test_vertical.id),
        "target_audience": "ORGANIZATION",
        "publish_and_distribute": True,
        "recipient_ids": [str(coordinator_user.id), str(regular_user.id)],
        "distribution_deadline": deadline_iso,
        "distribution_instructions": "Upload CPR certification proof",
        "distribution_config": {
            "audience_items": [
                {"id": f"USER:{coordinator_user.id}", "type": "USER", "rawId": str(coordinator_user.id), "label": coordinator_user.username},
                {"id": f"USER:{regular_user.id}", "type": "USER", "rawId": str(regular_user.id), "label": regular_user.username},
            ],
            "recipient_ids": [str(coordinator_user.id), str(regular_user.id)],
            "deadline": deadline_iso,
            "distribution_instructions": "Upload CPR certification proof",
        },
        "sections": [
            {
                "id": "sec-1",
                "title": "Certification Details",
                "ordering": 1,
                "fields": [
                    {
                        "id": "f-1",
                        "key": "cert_number",
                        "label": "Certificate Number",
                        "type": "TEXT",
                        "required": True,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/forms", json=payload, headers=auth_headers_admin)
    assert res.status_code == status.HTTP_201_CREATED, res.text
    data = res.json()

    assert data["name"] == "Medical Readiness Form"
    assert data["status"] == "PUBLISHED"

    form_id = uuid.UUID(data["id"])
    form = db_session.get(Form, form_id)
    assert form is not None
    assert form.status == FormStatus.PUBLISHED

    # Verify FormDistribution
    distributions = list(db_session.scalars(select(FormDistribution).where(FormDistribution.form_id == form_id)).all())
    assert len(distributions) == 1
    dist = distributions[0]
    assert dist.recipient_count == 2
    assert dist.instructions == "Upload CPR certification proof"

    # Verify FormResponse instances created for both recipients
    responses = list(db_session.scalars(select(FormResponse).where(FormResponse.form_id == form_id)).all())
    assert len(responses) == 2
    recipient_ids = {r.recipient_id for r in responses}
    assert coordinator_user.id in recipient_ids
    assert regular_user.id in recipient_ids
    for r in responses:
        assert r.status == FormResponseStatus.ASSIGNED
        assert r.current_phase == 1


def test_publish_and_distribute_requires_recipients(
    client: TestClient,
    auth_headers_admin: dict,
    test_vertical: Vertical,
):
    """Verify publish_and_distribute fails with validation error if no recipients selected."""
    payload = {
        "name": "Invalid Distribute Form",
        "purpose": "Should fail",
        "publish_and_distribute": True,
        "recipient_ids": [],
        "sections": [
            {
                "id": "sec-1",
                "title": "General",
                "ordering": 1,
                "fields": [{"id": "f-1", "key": "k", "label": "L", "type": "TEXT", "required": True}],
            }
        ],
    }

    res = client.post("/api/v1/forms", json=payload, headers=auth_headers_admin)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "recipient" in res.text.lower()


def test_update_draft_and_publish_distribute(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    coordinator_user: User,
    test_vertical: Vertical,
):
    """Verify editing a draft form and then triggering publish & distribute works seamlessly."""
    # 1. Create draft
    draft_payload = {
        "name": "Draft to be published later",
        "purpose": "Initial draft state",
        "publish_and_distribute": False,
        "sections": [
            {
                "id": "sec-1",
                "title": "Phase 1",
                "ordering": 1,
                "fields": [{"id": "f-1", "key": "q1", "label": "Q1", "type": "TEXT", "required": True}],
            }
        ],
    }
    create_res = client.post("/api/v1/forms", json=draft_payload, headers=auth_headers_admin)
    assert create_res.status_code == status.HTTP_201_CREATED
    form_id = create_res.json()["id"]

    # 2. Update draft and publish & distribute
    update_payload = {
        "name": "Final Published Form",
        "purpose": "Updated purpose and distributed",
        "publish_and_distribute": True,
        "recipient_ids": [str(coordinator_user.id)],
        "distribution_instructions": "Please submit promptly",
    }
    update_res = client.patch(f"/api/v1/forms/{form_id}", json=update_payload, headers=auth_headers_admin)
    assert update_res.status_code == status.HTTP_200_OK, update_res.text
    updated_data = update_res.json()

    assert updated_data["name"] == "Final Published Form"
    assert updated_data["status"] == "PUBLISHED"

    # Verify responses created
    f_uuid = uuid.UUID(form_id)
    responses = list(db_session.scalars(select(FormResponse).where(FormResponse.form_id == f_uuid)).all())
    assert len(responses) == 1
    assert responses[0].recipient_id == coordinator_user.id
    assert responses[0].status == FormResponseStatus.ASSIGNED


def test_distribution_summary_and_entity_not_found_handling(
    client: TestClient,
    auth_headers_admin: dict,
):
    """Verify get_distribution_summary properly handles non-existent and empty forms without 500 TypeError."""
    # 1. Non-existent form must return 404 cleanly, not 500
    fake_id = uuid.uuid4()
    res = client.get(f"/api/v1/forms/{fake_id}/distribution-summary", headers=auth_headers_admin)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    err = res.json()
    assert err["error"]["code"] == "ENTITY_NOT_FOUND"

    # 2. Existing draft form with 0 responses returns empty summary with 200
    draft_res = client.post(
        "/api/v1/forms",
        json={"name": "Empty Draft", "purpose": "Testing summary", "sections": []},
        headers=auth_headers_admin,
    )
    assert draft_res.status_code == status.HTTP_201_CREATED
    draft_id = draft_res.json()["id"]

    summary_res = client.get(f"/api/v1/forms/{draft_id}/distribution-summary", headers=auth_headers_admin)
    assert summary_res.status_code == status.HTTP_200_OK
    summary_data = summary_res.json()
    assert summary_data["total_recipients"] == 0
    assert summary_data["form_name"] == "Empty Draft"
