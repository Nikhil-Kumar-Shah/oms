"""
Phase 4 Operational Acceptance Tests: Requests + Meetings + Forms + Workflow Automation
Tests end-to-end operational workflows, cross-vertical requirements, escalation chains,
meeting request & review lifecycles, event team boundaries, idempotent task conversions,
form audience scoping, server-side validation, four-eyes review, atomic transformations,
and fresh-session PostgreSQL database verification.
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.models.communication import Notification, NotificationType
from app.models.event import Event, EventStatus, EventTeamProfile, EventType
from app.models.form import (
    Form,
    FormAudience,
    FormFieldType,
    FormStatus,
    FormSubmission,
    FormSubmissionStatus,
    FormVersion,
)
from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingParticipant,
    MeetingStatus,
    MeetingType,
    RSVPStatus,
)
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.requirement import (
    Requirement,
    RequirementPriority,
    RequirementStatus,
)
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.schemas.form import (
    FormCreate,
    FormFieldSchema,
    FormSubmissionCreate,
    FormSubmissionReviewRequest,
    FormTransformationConfig,
)
from app.schemas.meeting import (
    MeetingActionConvertToTaskRequest,
    MeetingActionItemCreate,
    MeetingCreate,
    MeetingParticipantCreate,
    MeetingRequestCreate,
    MeetingRescheduleRequest,
    MeetingReviewRequest,
    MeetingRSVPRequest,
)
from app.schemas.requirement import (
    RequirementAssignRequest,
    RequirementCreate,
    RequirementEscalateRequest,
    RequirementMessageCreate,
    RequirementResolveEscalationRequest,
    RequirementTransitionRequest,
)
from app.services.form_service import FormService
from app.services.meeting_service import MeetingService
from app.services.requirement_service import RequirementService


def _create_user(db: Session, username_prefix: str, role_name: str = "VOLUNTEER") -> User:
    uid = uuid4().hex[:6]
    u = User(
        username=f"{username_prefix}_{uid}",
        full_name=f"{username_prefix} {uid}",
        email=f"{username_prefix}_{uid}@example.com",
        password_hash="argon2id$mockhash",
        account_status=AccountStatus.ACTIVE,
    )
    db.add(u)
    db.flush()

    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        role = Role(name=role_name, display_name=role_name)
        db.add(role)
        db.flush()

    db.add(UserRole(user_id=u.id, role_id=role.id))
    db.flush()
    return u


def _create_org_and_verticals(db: Session):
    org = db.scalar(select(Organization).limit(1))
    if not org:
        org = Organization(name="Test Org", code=f"ORG_{uuid4().hex[:4]}")
        db.add(org)
        db.flush()

    v1 = Vertical(name=f"Logistics_{uuid4().hex[:4]}", organization_id=org.id, status=VerticalStatus.ACTIVE)
    v2 = Vertical(name=f"Medical_{uuid4().hex[:4]}", organization_id=org.id, status=VerticalStatus.ACTIVE)
    db.add_all([v1, v2])
    db.flush()
    return org, v1, v2


class TestPhase4RequirementsWorkflow:
    """Part A: Cross-Vertical Requirements, Escalation, Messages & Notifications."""

    def test_requirement_end_to_end_routing_assignment_and_notifications(self, db_session: Session):
        org, v1, v2 = _create_org_and_verticals(db_session)
        requester = _create_user(db_session, "req_user", "SPORTS_CORE")
        assignee = _create_user(db_session, "med_officer", "COORDINATOR")

        # Assign requester to v1, assignee to v2
        db_session.add(UserVertical(user_id=requester.id, vertical_id=v1.id, is_primary=True))
        db_session.add(UserVertical(user_id=assignee.id, vertical_id=v2.id, is_primary=True))
        db_session.flush()

        service = RequirementService(db_session)

        # 1. Create requirement (unassigned)
        create_data = RequirementCreate(
            title="First Aid Stations for Field 3",
            description="Require 2 medical staff and first aid kits.",
            requesting_vertical_id=v1.id,
            target_vertical_id=v2.id,
            priority=RequirementPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
        )
        req = service.create_requirement(create_data, requester_id=requester.id)
        assert req.status == RequirementStatus.OPEN
        assert req.assignee_id is None

        # 2. Assign requirement to assignee in target vertical
        service.assign_requirement(req.id, RequirementAssignRequest(assignee_id=assignee.id), actor_id=requester.id)
        assert req.status == RequirementStatus.ASSIGNED
        assert req.assignee_id == assignee.id

        # Verify assignee notification
        notif = db_session.scalar(
            select(Notification).where(
                Notification.recipient_id == assignee.id,
                Notification.notification_type == NotificationType.REQUIREMENT,
            )
        )
        assert notif is not None
        assert "Requirement Assigned" in notif.title

        # 3. Add message from assignee -> triggers counterparty notification to requester
        service.add_message(req.id, RequirementMessageCreate(content="Medical team dispatched to Field 3."), author_id=assignee.id)
        req_notif = db_session.scalar(
            select(Notification).where(
                Notification.recipient_id == requester.id,
                Notification.notification_type == NotificationType.REQUIREMENT,
            )
        )
        assert req_notif is not None

        # 4. Transition to COMPLETED
        service.transition_status(req.id, RequirementTransitionRequest(status=RequirementStatus.COMPLETED, remarks="Kit installed."), actor_id=assignee.id)
        assert req.status == RequirementStatus.COMPLETED

    def test_requirement_structured_escalation_and_resolution(self, db_session: Session):
        org, v1, v2 = _create_org_and_verticals(db_session)
        requester = _create_user(db_session, "requester_esc", "COORDINATOR")
        supervisor = _create_user(db_session, "supervisor_esc", "SPORTS_CORE")

        db_session.add(UserVertical(user_id=requester.id, vertical_id=v1.id, is_primary=True))
        db_session.add(UserVertical(user_id=supervisor.id, vertical_id=v2.id, is_primary=True))
        db_session.flush()

        service = RequirementService(db_session)
        req = service.create_requirement(
            RequirementCreate(
                title="Critical Power Supply for Pitch 1",
                description="Power outlet required.",
                requesting_vertical_id=v1.id,
                target_vertical_id=v2.id,
                priority=RequirementPriority.CRITICAL,
            ),
            requester_id=requester.id,
        )

        # 1. Escalate requirement to supervisor
        service.escalate_requirement(
            req.id,
            RequirementEscalateRequest(escalated_to_id=supervisor.id, reason="No response from field team after 4 hours."),
            actor_id=requester.id,
        )
        assert req.is_escalated is True
        assert req.escalated_to_id == supervisor.id
        assert req.escalation_status == "PENDING_REVIEW"

        # Verify supervisor notification
        sup_notif = db_session.scalar(
            select(Notification).where(
                Notification.recipient_id == supervisor.id,
                Notification.notification_type == NotificationType.REQUIREMENT,
            )
        )
        assert sup_notif is not None
        assert "Requirement Escalation" in sup_notif.title

        # 2. Resolve escalation
        service.resolve_requirement_escalation(
            req.id,
            RequirementResolveEscalationRequest(resolution_notes="Authorized generator dispatch from central inventory."),
            actor_id=supervisor.id,
        )
        assert req.is_escalated is False
        assert req.escalation_status == "RESOLVED"
        assert "Authorized generator" in req.escalation_resolution_notes

    def test_requirement_cross_vertical_violation_and_idor_rejection(self, db_session: Session):
        org, v1, v2 = _create_org_and_verticals(db_session)
        requester = _create_user(db_session, "user_v1", "COORDINATOR")
        outsider = _create_user(db_session, "outsider_v1", "COORDINATOR")

        # Both assigned to v1, but neither to v2
        db_session.add(UserVertical(user_id=requester.id, vertical_id=v1.id, is_primary=True))
        db_session.add(UserVertical(user_id=outsider.id, vertical_id=v1.id, is_primary=True))
        db_session.flush()

        service = RequirementService(db_session)
        req = service.create_requirement(
            RequirementCreate(
                title="Transport Request",
                description="Bus needed.",
                requesting_vertical_id=v1.id,
                target_vertical_id=v2.id,
            ),
            requester_id=requester.id,
        )

        # Attempt to assign outsider (who belongs to v1, not target v2) -> must raise ValidationException
        with pytest.raises(ValidationException) as exc:
            service.assign_requirement(req.id, RequirementAssignRequest(assignee_id=outsider.id), actor_id=requester.id)
        assert "not assigned to the target vertical division" in str(exc.value)


class TestPhase4MeetingWorkflow:
    """Part B: Meeting Requests, Approvals, Action Item -> Master Task Conversion."""

    def test_meeting_request_workflow_approval_and_participant_rsvp(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        requester = _create_user(db_session, "mtg_req_user", "COORDINATOR")
        approver = _create_user(db_session, "mtg_approver", "SPORTS_CORE")
        participant = _create_user(db_session, "mtg_participant", "VOLUNTEER")

        service = MeetingService(db_session)

        # 1. Submit meeting request
        req_data = MeetingRequestCreate(
            title="Pitch Preparation Sync",
            description="Review line marking and goal setups.",
            vertical_id=v1.id,
            meeting_date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            participant_ids=[participant.id],
        )
        meeting = service.request_meeting(req_data, requester_id=requester.id)
        assert meeting.status == MeetingStatus.REQUESTED
        assert meeting.is_requested is True

        # 2. Requester attempting self-approval raises ForbiddenException
        with pytest.raises(ForbiddenException) as exc:
            service.review_meeting_request(meeting.id, MeetingReviewRequest(status=MeetingStatus.SCHEDULED), reviewer_id=requester.id)
        assert "Self-review violation" in str(exc.value)

        # 3. Supervisor approves meeting
        service.review_meeting_request(meeting.id, MeetingReviewRequest(status=MeetingStatus.SCHEDULED), reviewer_id=approver.id)
        assert meeting.status == MeetingStatus.SCHEDULED

        # 4. Participant RSVPs
        service.update_rsvp(meeting.id, user_id=participant.id, data=MeetingRSVPRequest(rsvp_status=RSVPStatus.ACCEPTED, notes="Will attend"))
        p = db_session.scalar(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting.id,
                MeetingParticipant.user_id == participant.id,
            )
        )
        assert p.rsvp_status == RSVPStatus.ACCEPTED

    def test_event_team_meeting_request_routed_to_head_poc(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        head_poc = _create_user(db_session, "head_poc_user", "SUPER_COORDINATOR")
        team_user = _create_user(db_session, "team_captain", "EVENT_TEAM")

        event = Event(
            name=f"Football Cup {uuid4().hex[:4]}",
            event_type=EventType.TOURNAMENT,
            status=EventStatus.IN_PROGRESS,
            planned_date=date.today(),
            vertical_id=v1.id,
            primary_poc_id=head_poc.id,
            created_by_id=head_poc.id,
        )
        db_session.add(event)
        db_session.flush()

        profile = EventTeamProfile(
            user_id=team_user.id,
            event_id=event.id,
            team_name="Tigers FC",
            head_name="John Doe",
        )
        db_session.add(profile)
        db_session.flush()

        service = MeetingService(db_session)

        # Team requests meeting
        meeting = service.request_meeting(
            MeetingRequestCreate(
                title="Jersey Clash Clarification",
                description="Our away kit color question.",
                meeting_date=date.today() + timedelta(days=1),
            ),
            requester_id=team_user.id,
            current_user=team_user,
        )

        assert meeting.status == MeetingStatus.REQUESTED
        assert meeting.meeting_type == MeetingType.EVENT_TEAM_SYNC
        assert meeting.event_id == event.id
        assert meeting.organizer_id == head_poc.id

        # Verify Head POC received attention notification
        poc_notif = db_session.scalar(
            select(Notification).where(
                Notification.recipient_id == head_poc.id,
                Notification.notification_type == NotificationType.MEETING,
            )
        )
        assert poc_notif is not None
        assert "Meeting Request Received" in poc_notif.title

    def test_meeting_action_item_idempotent_conversion_to_master_task(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        organizer = _create_user(db_session, "mtg_lead", "SUPER_COORDINATOR")
        assignee = _create_user(db_session, "action_owner", "COORDINATOR")

        service = MeetingService(db_session)
        meeting = service.create_meeting(
            MeetingCreate(
                title="Post-Match Operations Review",
                vertical_id=v1.id,
                meeting_date=date.today(),
                participant_ids=[assignee.id],
            ),
            organizer_id=organizer.id,
        )

        # Create Action Item
        action_item = service.create_action_item(
            meeting.id,
            MeetingActionItemCreate(description="Collect and sanitize player bibs.", assignee_id=assignee.id, priority=TaskPriority.HIGH),
            actor_id=organizer.id,
        )
        assert action_item.is_converted is False

        # Convert to Master Task
        _, task = service.convert_action_item_to_task(
            meeting.id,
            action_item.id,
            MeetingActionConvertToTaskRequest(vertical_id=v1.id, assigned_to_id=assignee.id),
            actor_id=organizer.id,
        )
        assert task.task_type == TaskType.MEETING_FOLLOW_UP
        assert task.vertical_id == v1.id
        assert task.assigned_to_id == assignee.id
        assert action_item.is_converted is True
        assert action_item.converted_task_id == task.id

        # Duplicate conversion prevention
        with pytest.raises(ValidationException) as exc:
            service.convert_action_item_to_task(
                meeting.id,
                action_item.id,
                MeetingActionConvertToTaskRequest(vertical_id=v1.id, assigned_to_id=assignee.id),
                actor_id=organizer.id,
            )
        assert "already been converted" in str(exc.value)


class TestPhase4FormsWorkflow:
    """Part C: Forms Audience Scoping, Versioning, Review & Structured Transformation."""

    def test_form_audience_scoping_vertical_and_event_team_isolation(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        admin = _create_user(db_session, "form_admin", "ADMIN")
        team_user = _create_user(db_session, "form_team_user", "EVENT_TEAM")

        event = Event(
            name=f"Marathon {uuid4().hex[:4]}",
            event_type=EventType.TOURNAMENT,
            status=EventStatus.IN_PROGRESS,
            planned_date=date.today(),
            vertical_id=v1.id,
            created_by_id=admin.id,
        )
        db_session.add(event)
        db_session.flush()

        profile = EventTeamProfile(
            user_id=team_user.id,
            event_id=event.id,
            team_name="Runners Club",
            head_name="Jane Doe",
        )
        db_session.add(profile)
        db_session.flush()

        service = FormService(db_session)

        # 1. Internal Org Form (restricted to internal)
        internal_form = service.create_form(
            FormCreate(
                name="Internal Budget Request",
                purpose="Financial tracking",
                target_audience=FormAudience.ORGANIZATION,
                vertical_id=v1.id,
            ),
            owner_id=admin.id,
        )

        # 2. Event Team Form (accessible to event teams)
        event_team_form = service.create_form(
            FormCreate(
                name="Team Dietary Requirements",
                purpose="Catering info",
                target_audience=FormAudience.EVENT_TEAM,
                vertical_id=v1.id,
                initial_schema=[
                    FormFieldSchema(key="meal_type", label="Meal Type", type=FormFieldType.TEXT, required=True),
                ],
            ),
            owner_id=admin.id,
        )
        service.publish_form_version(event_team_form.id, 1, actor_id=admin.id)

        # Event Team listings must NOT include the internal organization form
        team_forms, _ = service.list_forms(current_user=team_user)
        assert internal_form.id not in [f.id for f in team_forms]
        assert event_team_form.id in [f.id for f in team_forms]

        # Event team attempting submission to internal form raises ForbiddenException
        with pytest.raises(ForbiddenException) as exc:
            service.submit_form(internal_form.id, FormSubmissionCreate(submission_data={"amount": 1000}), submitter_id=team_user.id, current_user=team_user)
        assert "do not have permission" in str(exc.value)

    def test_form_review_self_approval_prohibition_and_task_transformation(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        submitter = _create_user(db_session, "form_submitter", "COORDINATOR")
        reviewer = _create_user(db_session, "form_reviewer", "SPORTS_CORE")

        service = FormService(db_session)

        form = service.create_form(
            FormCreate(
                name="Equipment Maintenance Issue Form",
                purpose="Report field defects",
                target_audience=FormAudience.ALL,
                vertical_id=v1.id,
                initial_schema=[
                    FormFieldSchema(key="title", label="Issue Summary", type=FormFieldType.TEXT, required=True),
                    FormFieldSchema(key="description", label="Issue Details", type=FormFieldType.LONG_TEXT, required=True),
                ],
                transformation_config=FormTransformationConfig(
                    target_entity="TASK",
                    field_mappings={"title": "title", "description": "description"},
                ),
            ),
            owner_id=reviewer.id,
        )
        service.publish_form_version(form.id, 1, actor_id=reviewer.id)

        # Submit form
        submission = service.submit_form(
            form.id,
            FormSubmissionCreate(submission_data={"title": "Broken Sprinkler on Pitch A", "description": "Water leaking rapidly near midfield."}),
            submitter_id=submitter.id,
        )
        assert submission.status == FormSubmissionStatus.SUBMITTED

        # Submitter attempting self-review raises ForbiddenException
        with pytest.raises(ForbiddenException) as exc:
            service.review_submission(submission.id, reviewer_id=submitter.id, data=FormSubmissionReviewRequest(status=FormSubmissionStatus.APPROVED))
        assert "Self-review violation" in str(exc.value)

        # Reviewer approves submission with automatic transformation
        reviewed_sub = service.review_submission(
            submission.id,
            reviewer_id=reviewer.id,
            data=FormSubmissionReviewRequest(status=FormSubmissionStatus.APPROVED, execute_transformation=True),
        )
        assert reviewed_sub.status == FormSubmissionStatus.APPROVED
        assert reviewed_sub.transformed_entity_type == "TASK"
        assert reviewed_sub.transformed_entity_id is not None

        # Verify created Master Task
        transformed_task = db_session.get(Task, reviewed_sub.transformed_entity_id)
        assert transformed_task is not None
        assert transformed_task.title == "Broken Sprinkler on Pitch A"
        assert transformed_task.vertical_id == v1.id

    def test_form_transformation_into_event(self, db_session: Session):
        org, v1, _ = _create_org_and_verticals(db_session)
        submitter = _create_user(db_session, "camp_submitter", "COORDINATOR")
        reviewer = _create_user(db_session, "camp_reviewer", "SPORTS_CORE")

        service = FormService(db_session)

        form = service.create_form(
            FormCreate(
                name="New Sports Clinic Proposal",
                purpose="Submit new event proposals",
                target_audience=FormAudience.ORGANIZATION,
                vertical_id=v1.id,
                initial_schema=[
                    FormFieldSchema(key="name", label="Event Name", type=FormFieldType.TEXT, required=True),
                    FormFieldSchema(key="description", label="Event Description", type=FormFieldType.LONG_TEXT, required=True),
                ],
                transformation_config=FormTransformationConfig(
                    target_entity="EVENT",
                    field_mappings={"name": "name", "description": "description"},
                ),
            ),
            owner_id=reviewer.id,
        )
        service.publish_form_version(form.id, 1, actor_id=reviewer.id)

        submission = service.submit_form(
            form.id,
            FormSubmissionCreate(submission_data={"name": "Adaptive Archery Clinic 2026", "description": "Inclusive archery training for youth."}),
            submitter_id=submitter.id,
        )

        reviewed_sub = service.review_submission(
            submission.id,
            reviewer_id=reviewer.id,
            data=FormSubmissionReviewRequest(status=FormSubmissionStatus.APPROVED, execute_transformation=True),
        )
        assert reviewed_sub.transformed_entity_type == "EVENT"
        assert reviewed_sub.transformed_entity_id is not None

        created_event = db_session.get(Event, reviewed_sub.transformed_entity_id)
        assert created_event is not None
        assert created_event.name == "Adaptive Archery Clinic 2026"
        assert created_event.status == EventStatus.PLANNING


class TestPhase4DatabasePersistenceTruth:
    """Fresh session read verification of Phase 4 database entities."""

    def test_phase4_fresh_session_postgresql_persistence_truth(self, db_session: Session):
        org, v1, v2 = _create_org_and_verticals(db_session)
        u1 = _create_user(db_session, "fresh_user1", "SPORTS_CORE")
        u2 = _create_user(db_session, "fresh_user2", "COORDINATOR")

        db_session.add(UserVertical(user_id=u1.id, vertical_id=v1.id, is_primary=True))
        db_session.add(UserVertical(user_id=u2.id, vertical_id=v2.id, is_primary=True))
        db_session.commit()

        # Perform transactional requirement creation and escalation
        req_svc = RequirementService(db_session)
        req = req_svc.create_requirement(
            RequirementCreate(
                title="Ground Security Support",
                description="Perimeter security setup.",
                requesting_vertical_id=v1.id,
                target_vertical_id=v2.id,
                priority=RequirementPriority.CRITICAL,
            ),
            requester_id=u1.id,
        )
        req_svc.escalate_requirement(req.id, RequirementEscalateRequest(escalated_to_id=u1.id, reason="Security barrier delay."), actor_id=u2.id)
        db_session.commit()

        req_id = req.id

        # Close session and read in a completely new database session
        from app.core.database import SessionLocal
        fresh_db = SessionLocal()
        try:
            fresh_req = fresh_db.get(Requirement, req_id)
            assert fresh_req is not None
            assert fresh_req.title == "Ground Security Support"
            assert fresh_req.is_escalated is True
            assert fresh_req.escalated_to_id == u1.id
            assert fresh_req.escalation_reason == "Security barrier delay."
        finally:
            fresh_db.close()
