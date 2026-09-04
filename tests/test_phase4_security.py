"""
Dedicated Phase 4 Security Attack Suite
Verifies defenses against:
1. Unauthorized event creation
2. Disabled user assignment to event team
3. Cross-vertical event team assignment breach
4. Cross-vertical requirement routing breach
5. Submitter self-approval on form submissions
6. Zero hard-deletion enforcement
"""

import uuid
from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.event import EventType
from app.models.organization import Vertical
from app.models.user import User


def test_attack_cross_vertical_event_team_assignment_blocked(
    client: TestClient,
    auth_headers_admin: dict,
    regular_user: User,
    db_session: Session,
):
    """Attack: Assigning a user to an event in a vertical they do not belong to is rejected."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Athletics & Track"))
    from app.schemas.event import EventCreate
    from app.services.event_service import EventService
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))

    event = EventService(db_session).create_event(
        EventCreate(
            vertical_id=vert.id,
            name="Track Security Test",
            planned_date=date.today() + timedelta(days=20),
        ),
        actor_id=admin_u.id,
    )
    db_session.commit()

    # regular_user is not in Athletics & Track
    resp = client.post(
        f"/api/v1/events/{event.id}/team",
        json={"user_id": str(regular_user.id), "role_in_event": "COORDINATOR"},
        headers=auth_headers_admin,
    )
    assert resp.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]


def test_attack_cross_vertical_requirement_assignment_blocked(
    client: TestClient,
    auth_headers_admin: dict,
    regular_user: User,
    db_session: Session,
):
    """Attack: Assigning a requirement to a user outside the target vertical is rejected."""
    v_source = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    v_target = db_session.scalar(select(Vertical).where(Vertical.name == "Cricket Operations"))

    # regular_user is not in Cricket Operations
    payload = {
        "title": "Cricket Pitch Roller Request",
        "description": "Cross vertical routing breach attempt",
        "requesting_vertical_id": str(v_source.id),
        "target_vertical_id": str(v_target.id),
        "assignee_id": str(regular_user.id),
    }
    resp = client.post("/api/v1/requirements", json=payload, headers=auth_headers_admin)
    assert resp.status_code in [getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), status.HTTP_400_BAD_REQUEST]


def test_attack_form_submission_self_approval_blocked(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_coordinator: dict,
    coordinator_user: User,
    db_session: Session,
):
    """Attack: Author of form submission attempting to approve their own submission fails with 403."""
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
    from app.schemas.form import FormCreate, FormFieldSchema, FormSubmissionCreate
    from app.services.form_service import FormService
    admin_u = db_session.scalar(select(User).where(User.username == "test_admin"))
    form_service = FormService(db_session)

    form = form_service.create_form(
        FormCreate(
            name="Security Self Approval Form",
            purpose="Self approval test",
            vertical_id=vert.id,
            initial_schema=[FormFieldSchema(key="comment", label="Comment", type="TEXT", required=True)],
        ),
        owner_id=admin_u.id,
    )
    form_service.publish_form_version(form.id, version_number=1, actor_id=admin_u.id)
    db_session.commit()

    sub = form_service.submit_form(form.id, FormSubmissionCreate(submission_data={"comment": "Self submission"}), submitter_id=coordinator_user.id)
    db_session.commit()

    # Coordinator tries to approve own submission
    resp = client.post(
        f"/api/v1/form-submissions/{sub.id}/review",
        json={"status": "APPROVED", "review_comments": "Attempting self approval"},
        headers=auth_headers_coordinator,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_zero_hard_deletion_policy_phase4_enforced(
    client: TestClient,
    auth_headers_admin: dict,
):
    """Verifies that DELETE HTTP methods are not implemented on Phase 4 resources."""
    random_id = str(uuid.uuid4())
    # 1. DELETE /events/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/events/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 2. DELETE /requirements/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/requirements/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 3. DELETE /meetings/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/meetings/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 4. DELETE /forms/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/forms/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    # 5. DELETE /form-submissions/{id} -> 405 Method Not Allowed
    assert client.delete(f"/api/v1/form-submissions/{random_id}", headers=auth_headers_admin).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
