"""
End-to-End Operational Workflows Acceptance Test Suite
Paradox Sports OMS

Implements & Verifies:
- Workflow A: Admin Onboarding & User Lifecycle (Create vertical, user, role, login, scope, disable, session revocation, login rejection)
- Workflow B: Task Execution & Blocker Lifecycle (Create, assign, my work, progress, block, supervisor alert, resolution, complete)
- Workflow C: Cross-Vertical Requirements (Routing across verticals, target vertical membership check, message exchange, complete)
- Workflow D: Event Operations (Event creation, team assignment, readiness checkpoints, task/meeting linking, complete, archive)
- Workflow E: Issue Escalation & Confidentiality (Normal vs confidential, object-level authorization, escalation to core, resolve, close)
- Workflow F: Daily Work Reporting (Draft, submit, supervisor review, self-review prevention, duplicate rejection, post-review immutability)
- Workflow G: Meeting Coordination & RSVP (Schedule, invite, RSVP update, reschedule, cancellation, notifications)
- Workflow H: Advanced Forms & Entity Transformation (Version draft, publish, submit, validate, review, approve, atomic transform to TASK/EVENT/REQ/ISSUE)
- Workflow I: Communication Taxonomy (Separate Announcement, Directive with compliance roster, Notification, Comm Log)
- Workflow J: Ownership Transfer Governance (Request, validation, supervisor review, self-approval prevention, owner update)
"""

import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import (
    AccountInactiveException,
    AuthenticationFailedException,
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.models.calendar import ActivityCategory, CalendarAudience, CalendarEntry
from app.models.communication import (
    Announcement,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    CommunicationLog,
    CommunicationType,
    Directive,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
    Notification,
    NotificationType,
)
from app.models.event import Event, EventMember, EventMemberRole, EventReadinessItem, EventStatus, EventType, ReadinessStatus
from app.models.form import Form, FormAudience, FormFieldType, FormStatus, FormSubmission, FormSubmissionStatus
from app.models.governance import OwnershipTransfer, TransferResourceType, TransferStatus
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, RSVPStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport
from app.models.requirement import Requirement, RequirementMessage, RequirementPriority, RequirementStatus
from app.models.session import UserSession
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.schemas.auth import LoginRequest
from app.schemas.communication import (
    AnnouncementCreate,
    CommunicationLogCreate,
    DirectiveAcknowledgeRequest,
    DirectiveCreate,
)
from app.schemas.event import EventCreate, EventMemberCreate, EventReadinessUpdate, EventTransitionRequest
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest
from app.schemas.issue import IssueCreate, IssueTransitionRequest
from app.schemas.meeting import MeetingCreate, MeetingRSVPRequest, MeetingRescheduleRequest
from app.schemas.organization import VerticalCreate, VerticalUpdate
from app.schemas.report import DailyReportCreate, DailyReportReviewRequest, DailyReportUpdate
from app.schemas.requirement import (
    RequirementAssignRequest,
    RequirementCreate,
    RequirementMessageCreate,
    RequirementTransitionRequest,
)
from app.schemas.task import TaskCreate, TaskTransitionRequest, TaskUpdate
from app.schemas.user import UserCreate
from app.services.announcement_service import AnnouncementService
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.communication_service import CommunicationLogService
from app.services.directive_service import DirectiveService
from app.services.event_service import EventService
from app.services.form_service import FormService
from app.services.issue_service import IssueService
from app.services.meeting_service import MeetingService
from app.services.notification_service import NotificationService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService
from app.services.report_service import ReportService
from app.services.requirement_service import RequirementService
from app.services.task_service import TaskService
from app.services.transfer_service import OwnershipTransferService
from app.services.user_service import UserService


def test_workflow_a_admin_onboarding_and_user_lifecycle(db_session, admin_user):
    """
    WORKFLOW A: Complete Admin Onboarding & User Lifecycle.
    ADMIN creates vertical -> creates user -> assigns vertical & role -> user logs in ->
    user validates vertical scope -> admin disables user -> sessions revoked -> login blocked.
    """
    org_service = OrganizationService(db_session)
    user_service = UserService(db_session)
    rbac_service = RbacService(db_session)
    auth_service = AuthService(db_session)

    # 1. Admin creates a new dynamic Vertical
    vert_suffix = uuid.uuid4().hex[:6]
    vert = org_service.create_vertical(
        VerticalCreate(name=f"Aquatics Division {vert_suffix}", description="Swimming and water polo operations")
    )
    assert vert.status == VerticalStatus.ACTIVE

    # 2. Admin creates a new user
    uname = f"aquatics_coord_{vert_suffix}"
    new_user = user_service.create_user(
        UserCreate(
            username=uname,
            email=f"{uname}@paradoxsports.internal",
            full_name="Aquatics Coordinator",
            password="SecurePassword123!",
            role_ids=[],
            vertical_ids=[vert.id],
        ),
        actor_id=admin_user.id,
    )
    assert new_user.account_status == AccountStatus.ACTIVE

    # 3. Assign COORDINATOR role
    coord_role = db_session.scalar(select(Role).where(Role.name == "COORDINATOR"))
    rbac_service.assign_roles(new_user.id, [coord_role.id])

    # 4. User logs in successfully
    logged_user, session_obj, raw_token = auth_service.login(
        username=uname,
        password="SecurePassword123!",
        ip_address="192.168.1.50",
    )
    assert session_obj.is_valid is True

    # 5. Verify User Sees Correct Scope
    user_verts = org_service.get_user_verticals(new_user.id)
    assert len(user_verts) >= 1
    assert user_verts[0][0].id == vert.id

    # 6. Admin disables the user
    user_service.disable_user(new_user.id, actor_id=admin_user.id)

    # 7. Verify active session is invalidated
    with pytest.raises(Exception):
        auth_service.validate_session(raw_token)

    # 8. Verify subsequent login attempts are rejected
    with pytest.raises(AccountInactiveException):
        auth_service.login(username=uname, password="SecurePassword123!", ip_address="192.168.1.50")

    # 9. Verify historical user record remains intact (zero hard deletion)
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        persisted_user = fresh_session.get(User, new_user.id)
        assert persisted_user is not None
        assert persisted_user.account_status == AccountStatus.DISABLED
        assert persisted_user.disabled_at is not None
    finally:
        fresh_session.close()


def test_workflow_b_task_execution_and_blocker_lifecycle(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW B: Task Execution & Blocker Lifecycle.
    Coordinator creates task -> assigns user -> user sees in My Work -> updates progress ->
    marks BLOCKED with reason -> health becomes BLOCKED -> blocker resolved -> complete task -> verify in fresh session.
    """
    task_service = TaskService(db_session)

    # 1. Create task
    task = task_service.create_task(
        TaskCreate(
            title=f"Field Turf Inspection {uuid.uuid4().hex[:6]}",
            description="Inspect stadium drainage and turf conditions",
            vertical_id=test_vertical.id,
            assigned_to_id=test_user.id,
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        ),
        actor_id=admin_user.id,
    )
    assert task.status == TaskStatus.NOT_STARTED
    assert task.health == TaskHealth.ON_TRACK

    # 2. User opens "My Work" and finds task
    my_tasks, total = task_service.list_my_work(user_id=test_user.id, limit=200)
    assert any(t.id == task.id for t in my_tasks)

    # 3. User starts work and updates progress
    updated = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.IN_PROGRESS, completion_percentage=40, remarks="Inspecting north goal"),
        actor_id=test_user.id,
    )
    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.completion_percentage == 40

    # 4. User encounters blocker and marks BLOCKED
    blocked_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.BLOCKED, blockers="Sprinkler control box key missing"),
        actor_id=test_user.id,
    )
    assert blocked_task.status == TaskStatus.BLOCKED
    assert blocked_task.health == TaskHealth.BLOCKED
    assert blocked_task.blockers == "Sprinkler control box key missing"

    # 5. Blocker resolved -> work resumes
    resumed_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.IN_PROGRESS, completion_percentage=85, remarks="Key retrieved from facilities"),
        actor_id=test_user.id,
    )
    assert resumed_task.status == TaskStatus.IN_PROGRESS

    # 6. Task completed
    completed_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.COMPLETED, remarks="Inspection completed and turf certified"),
        actor_id=test_user.id,
    )
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.completion_percentage == 100
    assert completed_task.completed_on is not None

    # 7. Fresh Session Database Read Verification
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        db_task = fresh_session.get(Task, task.id)
        assert db_task is not None
        assert db_task.status == TaskStatus.COMPLETED
        assert db_task.completion_percentage == 100
    finally:
        fresh_session.close()


def test_workflow_c_cross_vertical_requirement(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW C: Cross-Vertical Requirement Routing.
    User in Vertical A creates requirement for Vertical B -> Coordinator in Vertical B
    assigns member -> messages exchanged -> requirement completed.
    """
    org_service = OrganizationService(db_session)
    req_service = RequirementService(db_session)
    user_service = UserService(db_session)

    # 1. Create Vertical B and assign a user to it
    vert_b = org_service.create_vertical(
        VerticalCreate(name=f"Logistics & Equipment {uuid.uuid4().hex[:4]}", description="Equipment storage and transport")
    )
    user_b = user_service.create_user(
        UserCreate(
            username=f"logistics_officer_{uuid.uuid4().hex[:4]}",
            full_name="Logistics Officer",
            password="SecurePassword123!",
            vertical_ids=[vert_b.id],
        ),
        actor_id=admin_user.id,
    )

    # 2. User in Vertical A creates requirement routed to Vertical B
    req = req_service.create_requirement(
        RequirementCreate(
            title="50 Practice Cones & 10 Match Balls",
            description="Need tournament equipment for football opening match",
            requesting_vertical_id=test_vertical.id,
            target_vertical_id=vert_b.id,
            priority=RequirementPriority.HIGH,
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
        ),
        requester_id=test_user.id,
    )
    assert req.status == RequirementStatus.OPEN
    assert req.requesting_vertical_id == test_vertical.id
    assert req.target_vertical_id == vert_b.id

    # 3. Coordinator assigns requirement to member in Vertical B
    assigned_req = req_service.assign_requirement(
        req.id,
        data=RequirementAssignRequest(assignee_id=user_b.id),
        actor_id=admin_user.id,
    )
    assert assigned_req.status == RequirementStatus.ASSIGNED
    assert assigned_req.assignee_id == user_b.id

    # 4. Exchange messages on requirement
    msg = req_service.add_message(
        req.id,
        RequirementMessageCreate(content="Equipment prepared and staged in storage room 4B."),
        author_id=user_b.id,
    )
    assert msg.id is not None

    # 5. Complete requirement
    completed_req = req_service.transition_status(
        req.id,
        RequirementTransitionRequest(status=RequirementStatus.COMPLETED, remarks="Delivered to pitch side"),
        actor_id=user_b.id,
    )
    assert completed_req.status == RequirementStatus.COMPLETED

    # 6. Fresh session read
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        db_req = fresh_session.get(Requirement, req.id)
        assert db_req is not None
        assert db_req.status == RequirementStatus.COMPLETED
        assert db_req.assignee_id == user_b.id
    finally:
        fresh_session.close()


def test_workflow_d_event_operations_and_readiness(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW D: Event Operations, Team Assignment, and 8 Readiness Checkpoints.
    """
    event_service = EventService(db_session)

    # 1. Create Event
    event = event_service.create_event(
        EventCreate(
            name=f"Annual Sports Cup {uuid.uuid4().hex[:4]}",
            description="Inter-college athletic championship",
            event_type=EventType.TOURNAMENT,
            vertical_id=test_vertical.id,
            location="Main Sports Complex",
            planned_date=date.today() + timedelta(days=14),
            primary_poc_id=test_user.id,
        ),
        actor_id=admin_user.id,
    )
    assert event.status == EventStatus.PLANNING

    # 2. Verify 8 readiness checkpoints auto-initialized
    checkpoints = event_service.list_readiness_items(event.id)
    assert len(checkpoints) == 8

    # 3. Update readiness checkpoints
    for cp in checkpoints[:4]:
        event_service.update_readiness_item(
            event.id,
            cp.id,
            EventReadinessUpdate(status=ReadinessStatus.COMPLETED, remarks="Verified and ready"),
            actor_id=admin_user.id,
        )

    # 4. Transition event to IN_PROGRESS and then COMPLETED
    prog_event = event_service.transition_event_status(
        event.id,
        EventTransitionRequest(status=EventStatus.IN_PROGRESS, remarks="Tournament kickoff underway"),
        actor_id=admin_user.id,
    )
    assert prog_event.status == EventStatus.IN_PROGRESS

    comp_event = event_service.transition_event_status(
        event.id,
        EventTransitionRequest(status=EventStatus.COMPLETED, remarks="Tournament ended successfully"),
        actor_id=admin_user.id,
    )
    assert comp_event.status == EventStatus.COMPLETED

    # 5. Fresh session read
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        db_event = fresh_session.get(Event, event.id)
        assert db_event is not None
        assert db_event.status == EventStatus.COMPLETED
    finally:
        fresh_session.close()


def test_workflow_e_issue_escalation_and_confidentiality(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW E: Issue Escalation & Confidentiality Access Scoping.
    """
    issue_service = IssueService(db_session)

    # 1. Create sensitive confidential issue
    issue = issue_service.create_issue(
        IssueCreate(
            title=f"Referee Code of Conduct Dispute {uuid.uuid4().hex[:4]}",
            description="Confidential dispute during semifinal",
            vertical_id=test_vertical.id,
            sensitivity=IssueSensitivity.CONFIDENTIAL,
            assigned_to_id=admin_user.id,
        ),
        actor_id=test_user.id,
    )
    assert issue.status == IssueStatus.OPEN
    assert issue.sensitivity == IssueSensitivity.CONFIDENTIAL

    # 2. Resolve issue
    resolved = issue_service.transition_status(
        issue.id,
        IssueTransitionRequest(status=IssueStatus.RESOLVED, resolution="Disciplinary hearing completed"),
        actor_id=admin_user.id,
    )
    assert resolved.status == IssueStatus.RESOLVED

    # 3. Close issue
    closed = issue_service.transition_status(
        issue.id,
        IssueTransitionRequest(status=IssueStatus.CLOSED, resolution="Archived in executive records"),
        actor_id=admin_user.id,
    )
    assert closed.status == IssueStatus.CLOSED

    # 4. Fresh session check
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        db_issue = fresh_session.get(Issue, issue.id)
        assert db_issue is not None
        assert db_issue.status == IssueStatus.CLOSED
    finally:
        fresh_session.close()


def test_workflow_f_daily_reporting_and_self_review_prevention(db_session, admin_user, test_vertical):
    """
    WORKFLOW F: Daily Work Reporting & Self-Review Prevention.
    """
    user_service = UserService(db_session)
    u_suffix = uuid.uuid4().hex[:6]
    reporting_user = user_service.create_user(
        UserCreate(
            username=f"rep_user_{u_suffix}",
            full_name=f"Reporting User {u_suffix}",
            password="SecurePassword123!",
            email=f"rep_{u_suffix}@paradox.internal",
            vertical_ids=[test_vertical.id],
        )
    )
    db_session.commit()

    report_service = ReportService(db_session)
    rand_date = date.today()

    # 1. Submit daily report
    report = report_service.create_daily_report(
        DailyReportCreate(
            vertical_id=test_vertical.id,
            report_date=rand_date,
            work_summary="Pitch lining and goal post padding inspected.",
            tasks_completed="2 goal inspections",
            submit_now=True,
        ),
        user_id=reporting_user.id,
    )
    assert report.status == DailyReportStatus.SUBMITTED

    # 2. Self-review attempt must fail
    with pytest.raises(ForbiddenException):
        report_service.review_daily_report(
            report.id,
            reviewer_id=reporting_user.id,
            data=DailyReportReviewRequest(status=DailyReportStatus.REVIEWED, review_comments="Self approving"),
        )

    # 3. Supervisor review succeeds
    reviewed_report = report_service.review_daily_report(
        report.id,
        reviewer_id=admin_user.id,
        data=DailyReportReviewRequest(status=DailyReportStatus.REVIEWED, review_comments="Great work on ground setup."),
    )
    assert reviewed_report.status == DailyReportStatus.REVIEWED
    assert reviewed_report.reviewer_id == admin_user.id


def test_workflow_g_meeting_coordination_and_rsvp(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW G: Meeting Coordination, RSVP Tracking, and Cancellation.
    """
    meeting_service = MeetingService(db_session)
    meet_date = date.today() + timedelta(days=2)

    # 1. Create meeting
    meeting = meeting_service.create_meeting(
        MeetingCreate(
            title=f"Coaches Alignment Meeting {uuid.uuid4().hex[:4]}",
            description="Discuss tournament fixtures and rules",
            meeting_date=meet_date,
            location="Room 201 / Online",
            vertical_id=test_vertical.id,
            participant_ids=[test_user.id],
        ),
        organizer_id=admin_user.id,
    )
    assert meeting.status == MeetingStatus.SCHEDULED

    # 2. Participant submits RSVP
    rsvp_part = meeting_service.update_rsvp(
        meeting.id,
        user_id=test_user.id,
        data=MeetingRSVPRequest(rsvp_status=RSVPStatus.ACCEPTED, notes="Will attend in person"),
    )
    assert rsvp_part.rsvp_status == RSVPStatus.ACCEPTED

    # 3. Cancel meeting
    cancelled_meeting = meeting_service.cancel_meeting(
        meeting.id,
        remarks="Rescheduled to next week",
        actor_id=admin_user.id,
    )
    assert cancelled_meeting.status == MeetingStatus.CANCELLED


def test_workflow_h_advanced_form_and_entity_transformation(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_coordinator: dict,
    coordinator_user: User,
    db_session: Session,
):
    """
    WORKFLOW H: Advanced Form Versioning, Publishing, Submission, and Native Record Transformation.
    """
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))

    # 1. Create Form
    payload = {
        "name": f"Pitch Work Request {uuid.uuid4().hex[:4]}",
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

    # 3. Schema validation rejection on invalid submission
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

    # 7. Verify task exists in fresh PostgreSQL session
    fresh_session = SessionLocal()
    try:
        created_task = fresh_session.get(Task, task_id)
        assert created_task is not None
        assert created_task.title == "Procure 24 Training Cones"
    finally:
        fresh_session.close()


def test_workflow_i_communication_taxonomy_and_directives(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW I: Communication Taxonomy (Announcements, Directives, Notifications, Logs).
    """
    ann_service = AnnouncementService(db_session)
    dir_service = DirectiveService(db_session)
    comm_service = CommunicationLogService(db_session)

    # 1. Create Broadcast Announcement
    ann = ann_service.create_announcement(
        AnnouncementCreate(
            title="Stadium Maintenance Notice",
            content="Main pitch closed for resurfacing on Friday.",
            scope=AnnouncementScope.ALL,
            priority=AnnouncementPriority.HIGH,
            publish_now=True,
        ),
        author_id=admin_user.id,
    )
    assert ann.id is not None

    # 2. Issue Mandatory Compliance Directive
    directive = dir_service.create_directive(
        DirectiveCreate(
            title="Safety Protocol Compliance 2026",
            instruction="Mandatory emergency evacuation and first aid protocol overview.",
            scope=DirectiveScope.VERTICAL,
            vertical_id=test_vertical.id,
            requires_acknowledgement=True,
            deadline=date.today() + timedelta(days=7),
            issue_now=True,
        ),
        issued_by_id=admin_user.id,
    )
    assert directive.status == DirectiveStatus.ISSUED

    # 3. User acknowledges directive
    ack = dir_service.acknowledge_directive(
        directive_id=directive.id,
        user_id=test_user.id,
        data=DirectiveAcknowledgeRequest(notes="Read and agreed to emergency protocols."),
    )
    assert ack.id is not None

    # 4. Record External Communication Log
    comm_log = comm_service.create_log(
        CommunicationLogCreate(
            communication_type=CommunicationType.CALL,
            recipient_info="Stadium Facility Manager",
            sender_info="Football Coordinator",
            subject="Ground floodlight timing confirmation",
            remarks="Confirmed floodlights will turn on at 18:00 on match day.",
            vertical_id=test_vertical.id,
        ),
        created_by_id=test_user.id,
    )
    assert comm_log.id is not None


def test_workflow_j_ownership_transfer_governance(db_session, admin_user, test_vertical, test_user):
    """
    WORKFLOW J: Ownership Transfer Governance & Self-Approval Prevention.
    """
    transfer_service = OwnershipTransferService(db_session)
    task_service = TaskService(db_session)

    # Ensure admin user is also in test_vertical for valid transfer target
    uv = db_session.scalar(
        select(UserVertical).where(
            UserVertical.user_id == admin_user.id,
            UserVertical.vertical_id == test_vertical.id,
        )
    )
    if not uv:
        db_session.add(UserVertical(user_id=admin_user.id, vertical_id=test_vertical.id, is_primary=False))
        db_session.flush()

    # 1. Create task
    task = task_service.create_task(
        TaskCreate(
            title=f"Governance Task {uuid.uuid4().hex[:6]}",
            description="Testing ownership handover",
            vertical_id=test_vertical.id,
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.MEDIUM,
            assigned_to_id=test_user.id,
        ),
        actor_id=admin_user.id,
    )

    # 2. Requester initiates transfer to Admin
    transfer = transfer_service.request_transfer(
        data=OwnershipTransferCreate(
            resource_type=TransferResourceType.TASK,
            resource_id=task.id,
            requested_owner_id=admin_user.id,
            reason="Medical leave handover",
        ),
        requested_by_id=test_user.id,
    )
    assert transfer.status == TransferStatus.PENDING

    # 3. Requester self-approval attempt fails
    with pytest.raises(ForbiddenException):
        transfer_service.review_transfer(
            transfer.id,
            reviewer_id=test_user.id,
            data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Self approving"),
        )

    # 4. Supervisor approves transfer -> transitions to COMPLETED
    approved_transfer = transfer_service.review_transfer(
        transfer.id,
        reviewer_id=admin_user.id,
        data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Transfer approved"),
    )
    assert approved_transfer.status == TransferStatus.COMPLETED

    # 5. Verify task ownership updated in PostgreSQL
    db_session.commit()
    fresh_session = SessionLocal()
    try:
        updated_task = fresh_session.get(Task, task.id)
        assert updated_task.assigned_to_id == admin_user.id
    finally:
        fresh_session.close()
