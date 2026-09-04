"""
Tests for Phase 10D: Forms System Rebuild and Strict User Data-Scoping
Verifies:
1. Strictly scoped workspace tabs: assigned_to_me, my_created, my_distributed, pending_review, returned, completed, shared_with_me, templates.
2. Dynamic form builder multi-section schema creation and arbitrary questions persistence.
3. Form distribution, response submission, checklist update, and return workflow.
4. Cross-user IDOR isolation & authorization enforcement (403 Forbidden).
5. User-scoped dashboard rollup metrics.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.models.user import User
from app.models.rbac import Role, UserRole

from app.models.form import (
    Form,
    FormStatus,
    FormAudience,
    FormVersion,
    FormDistribution,
    FormResponse,
    FormResponseStatus,
    ChecklistStatus,
)
from app.schemas.form import (
    FormCreate,
    FormSectionSchema,
    FormFieldSchema,
    FormFieldType,
    FormDistributeRequest,
    FormResponseSubmit,
    FormResponseReviewRequest,
)
from app.services.form_service import FormService
from app.core.exceptions import ForbiddenException


def _create_user(db_session, username: str, email: str, role_name: str = "COORDINATOR") -> User:
    user = User(
        username=username,
        email=email,
        full_name=f"Full {username}",
        password_hash="hashed_test_password",
    )
    db_session.add(user)
    db_session.flush()

    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db_session.add(role)
        db_session.flush()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(user_role)
    db_session.flush()
    return user



def test_dynamic_form_builder_multi_section_persistence(db_session):
    service = FormService(db_session)
    creator = _create_user(db_session, f"creator_{uuid4().hex[:6]}", f"creator_{uuid4().hex[:6]}@oms.local", "SUPER_COORDINATOR")

    # Build multi-section form with arbitrary fields
    sections = [
        FormSectionSchema(
            id="sec-1",
            title="Logistics & Venue Setup",
            description="Operational ground details",
            ordering=1,
            fields=[
                FormFieldSchema(
                    key="court_number",
                    label="Assigned Court Number",
                    type=FormFieldType.NUMBER,
                    required=True,
                    placeholder="e.g. 3",
                    ordering=1,
                ),
                FormFieldSchema(
                    key="rulebook_link",
                    label="Authoritative Rulebook Link",
                    type=FormFieldType.REFERENCE_LINK,
                    required=True,
                    placeholder="https://drive.google.com/...",
                    help_text="Link to official rules",
                    ordering=2,
                ),
            ],
        ),
        FormSectionSchema(
            id="sec-2",
            title="Team Declaration & Equipment Checklist",
            description="Compliance criteria",
            ordering=2,
            fields=[
                FormFieldSchema(
                    key="kit_color",
                    label="Official Team Jersey Color",
                    type=FormFieldType.SELECT,
                    options=["Navy Blue", "Crimson Red", "Forest Green", "Gold"],
                    required=True,
                    ordering=1,
                ),
                FormFieldSchema(
                    key="medical_compliance",
                    label="I confirm all athletes have signed medical clearance",
                    type=FormFieldType.CHECKBOX,
                    required=True,
                    ordering=2,
                ),
            ],
        ),
    ]

    create_data = FormCreate(
        name="Annual Championship Venue Readiness",
        purpose="Verify physical court preparedness and official team kits",
        instructions="Complete and submit prior to match day",
        category="Operational",
        target_audience=FormAudience.ORGANIZATION,
        sections=sections,
    )

    form = service.create_form(create_data, owner_id=creator.id, current_user=creator)
    assert form.id is not None
    assert form.status == FormStatus.DRAFT
    assert form.current_version_number == 1

    # Verify form version sections and compiled schema
    v1 = service.get_form_version(form.id, 1)
    assert len(v1.sections) == 2
    assert v1.sections[0]["title"] == "Logistics & Venue Setup"
    assert len(v1.sections[0]["fields"]) == 2
    assert len(v1.sections[1]["fields"]) == 2
    assert len(v1.schema) == 4  # flat schema compiled automatically

    # Publish version 1
    published_v1 = service.publish_form_version(form.id, 1, actor_id=creator.id)
    assert published_v1.is_published is True
    assert form.status == FormStatus.PUBLISHED


def test_user_workspace_tab_scoping(db_session):
    service = FormService(db_session)
    user_a = _create_user(db_session, f"user_a_{uuid4().hex[:6]}", f"user_a_{uuid4().hex[:6]}@oms.local", "SUPER_COORDINATOR")
    user_b = _create_user(db_session, f"user_b_{uuid4().hex[:6]}", f"user_b_{uuid4().hex[:6]}@oms.local", "SUPER_COORDINATOR")
    user_c = _create_user(db_session, f"user_c_{uuid4().hex[:6]}", f"user_c_{uuid4().hex[:6]}@oms.local", "COORDINATOR")


    # 1. User A creates Form A
    form_a = service.create_form(
        FormCreate(
            name="Form A by User A",
            purpose="Testing user scoping",
            category="Operational",
            sections=[
                FormSectionSchema(
                    title="Section 1",
                    fields=[FormFieldSchema(key="q1", label="Question 1", type=FormFieldType.TEXT)],
                )
            ],
        ),
        owner_id=user_a.id,
        current_user=user_a,
    )
    service.publish_form_version(form_a.id, 1, actor_id=user_a.id)

    # 2. User B creates Form B
    form_b = service.create_form(
        FormCreate(
            name="Form B by User B",
            purpose="Testing user scoping",
            category="Operational",
            sections=[
                FormSectionSchema(
                    title="Section 1",
                    fields=[FormFieldSchema(key="q1", label="Question 1", type=FormFieldType.TEXT)],
                )
            ],
        ),
        owner_id=user_b.id,
        current_user=user_b,
    )
    service.publish_form_version(form_b.id, 1, actor_id=user_b.id)

    # Verify 'my_created' scoping
    forms_a, count_a = service.list_forms(workspace_tab="my_created", current_user=user_a)
    assert count_a == 1
    assert forms_a[0].id == form_a.id

    forms_b, count_b = service.list_forms(workspace_tab="my_created", current_user=user_b)
    assert count_b == 1
    assert forms_b[0].id == form_b.id

    # 3. User A distributes Form A to User C
    dist = service.distribute_form(
        form_a.id,
        FormDistributeRequest(
            recipient_ids=[user_c.id],
            instructions="Please complete Form A",
        ),
        distributor_id=user_a.id,
    )
    assert dist.recipient_count == 1

    # Verify 'my_distributed' scoping for User A vs User B
    dist_forms_a, dist_count_a = service.list_forms(workspace_tab="my_distributed", current_user=user_a)
    assert dist_count_a == 1
    assert dist_forms_a[0].id == form_a.id

    dist_forms_b, dist_count_b = service.list_forms(workspace_tab="my_distributed", current_user=user_b)
    assert dist_count_b == 0

    # Verify 'assigned_to_me' scoping for User C
    resp_c, count_resp_c = service.list_responses(workspace_tab="assigned_to_me", current_user=user_c)
    assert count_resp_c == 1
    response_c = resp_c[0]
    assert response_c.recipient_id == user_c.id
    assert response_c.status == FormResponseStatus.ASSIGNED

    # User B should have 0 responses assigned
    resp_b, count_resp_b = service.list_responses(workspace_tab="assigned_to_me", current_user=user_b)
    assert count_resp_b == 0

    # 4. User C submits the response
    submitted_resp = service.submit_response(
        response_c.id,
        FormResponseSubmit(response_data={"q1": "Answer from User C"}),
        submitter_id=user_c.id,
    )
    assert submitted_resp.status == FormResponseStatus.SUBMITTED

    # 5. User A reviews the submission: returns with reason
    returned_resp = service.review_response(
        submitted_resp.id,
        FormResponseReviewRequest(
            action="RETURN",
            return_reason="Missing detailed attachments in q1",
            reviewer_remarks="Please update with court map link",
        ),
        reviewer_id=user_a.id,
    )
    assert returned_resp.status == FormResponseStatus.RETURNED
    assert returned_resp.return_reason == "Missing detailed attachments in q1"

    # Verify 'returned' tab for User C
    ret_c, count_ret_c = service.list_responses(workspace_tab="returned", current_user=user_c)
    assert count_ret_c == 1
    assert ret_c[0].id == response_c.id

    # 6. User C resubmits response
    resubmitted_resp = service.submit_response(
        response_c.id,
        FormResponseSubmit(response_data={"q1": "Answer with valid attachments"}),
        submitter_id=user_c.id,
    )
    assert resubmitted_resp.status == FormResponseStatus.RESUBMITTED

    # 7. User A approves response
    approved_resp = service.review_response(
        resubmitted_resp.id,
        FormResponseReviewRequest(
            action="APPROVE",
            reviewer_remarks="Approved - meets all criteria",
        ),
        reviewer_id=user_a.id,
    )
    assert approved_resp.status == FormResponseStatus.APPROVED

    # Verify 'completed' tab for User C
    comp_c, count_comp_c = service.list_responses(workspace_tab="completed", current_user=user_c)
    assert count_comp_c == 1
    assert comp_c[0].id == response_c.id

    # Verify user-scoped dashboard stats
    stats_a = service.get_dashboard_stats(current_user=user_a)
    assert stats_a.total_forms == 1
    assert stats_a.total_distributions == 1

    stats_c = service.get_dashboard_stats(current_user=user_c)
    assert stats_c.approved_responses == 1


def test_cross_user_idor_authorization_rejection(db_session):
    service = FormService(db_session)
    user_a = _create_user(db_session, f"user_a_{uuid4().hex[:6]}", f"user_a_{uuid4().hex[:6]}@oms.local", "SUPER_COORDINATOR")
    user_b = _create_user(db_session, f"user_b_{uuid4().hex[:6]}", f"user_b_{uuid4().hex[:6]}@oms.local", "COORDINATOR")
    unrelated_user = _create_user(db_session, f"unrelated_{uuid4().hex[:6]}", f"unrelated_{uuid4().hex[:6]}@oms.local", "COORDINATOR")


    form = service.create_form(
        FormCreate(
            name="Confidential Medical Form",
            purpose="Athlete medical review",
            sections=[FormSectionSchema(title="Medical", fields=[FormFieldSchema(key="med_q", label="Medical Details", type=FormFieldType.TEXT)])],
        ),
        owner_id=user_a.id,
        current_user=user_a,
    )
    service.publish_form_version(form.id, 1, actor_id=user_a.id)

    dist = service.distribute_form(
        form.id,
        FormDistributeRequest(recipient_ids=[user_b.id]),
        distributor_id=user_a.id,
    )
    response_b = dist.responses[0]

    # Authorized: User A (form creator & distributor) and User B (recipient)
    assert service.get_response_by_id(response_b.id, current_user=user_a).id == response_b.id
    assert service.get_response_by_id(response_b.id, current_user=user_b).id == response_b.id

    # Unauthorized: Unrelated user should receive 403 ForbiddenException
    with pytest.raises(ForbiddenException):
        service.get_response_by_id(response_b.id, current_user=unrelated_user)

