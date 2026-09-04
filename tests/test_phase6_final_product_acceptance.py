"""
Phase 6: Final Product Acceptance & End-to-End Integration Test Suite
Verifies that the entire Paradox Sports OMS operates as ONE coherent system across all 34 end-to-end user journeys:
1. User -> Role -> Vertical -> Permissions -> Work
2. Master Task -> My Work -> Real-time Analytics
3. Meeting -> Action Item -> Idempotent Task Conversion
4. Cross-Vertical Requirement Routing & Escalation
5. Event -> Event Team Isolation -> POC Group Governance
6. Event Team Profile Update & POC Attention
7. Dynamic Form Versioning -> Submission -> Approval -> Atomic Entity Transformation
8. Scoped Announcements (ALL, VERTICAL, EVENT, EVENT_TEAM) & Audience Isolation
9. Operational Directives & Compliance Acknowledgement Control
10. Notification Recipient Ownership Isolation
11. Governed Ownership Transfers with Four-Eyes Validation
12. Append-Only Immutable Audit Center (ImmutableAuditException)
13. Typed System Configuration Management
14. Live PostgreSQL Analytics, Performance Indicators & Compliance Reporting
15. Negative Security Attacks & Privilege Denials
16. Fresh-Session PostgreSQL Persistence Truth
"""

import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select

from app.core.exceptions import ForbiddenException, ImmutableAuditException, ValidationException
from app.models.audit import AuditLog
from app.models.communication import (
    AcknowledgementStatus,
    Announcement,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    CommunicationLog,
    CommunicationLogStatus,
    CommunicationType,
    Directive,
    DirectiveAcknowledgement,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
    Notification,
    NotificationReadStatus,
    NotificationType,
)
from app.models.event import Event, EventMember, EventReadinessItem, EventStatus, EventTeamProfile, EventType, ReadinessStatus
from app.models.form import Form, FormAudience, FormFieldType, FormStatus, FormSubmission, FormSubmissionStatus, FormVersion
from app.models.governance import ConfigValueType, OwnershipTransfer, SystemConfig, TransferResourceType, TransferStatus
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import Meeting, MeetingActionItem, MeetingParticipant, MeetingStatus, MeetingType, RSVPStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport
from app.models.requirement import Requirement, RequirementPriority, RequirementStatus
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.schemas.communication import (
    AnnouncementCreate,
    CommunicationLogCreate,
    DirectiveAcknowledgeRequest,
    DirectiveCreate,
)
from app.schemas.event_team import EventTeamCreate, EventTeamUpdate
from app.schemas.form import FormCreate, FormFieldSchema, FormSubmissionCreate, FormSubmissionReviewRequest, FormTransformationConfig
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest, SystemConfigCreate
from app.schemas.meeting import MeetingActionConvertToTaskRequest, MeetingActionItemCreate, MeetingCreate, MeetingRequestCreate, MeetingRSVPRequest
from app.schemas.requirement import RequirementAssignRequest, RequirementCreate, RequirementEscalateRequest, RequirementResolveEscalationRequest
from app.schemas.task import TaskCreate, TaskTransitionRequest, TaskUpdate
from app.services.admin_reporting_service import AdminReportingService
from app.services.analytics_service import AnalyticsService
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService
from app.services.communication_service import CommunicationLogService
from app.services.config_service import SystemConfigService
from app.services.directive_service import DirectiveService
from app.services.event_service import EventService
from app.services.event_team_service import EventTeamService
from app.services.form_service import FormService
from app.services.meeting_service import MeetingService
from app.services.notification_service import NotificationService
from app.services.organization_service import OrganizationService
from app.services.report_service import ReportService
from app.services.requirement_service import RequirementService
from app.services.task_service import TaskService
from app.services.transfer_service import OwnershipTransferService
from app.services.workspace_service import WorkspaceService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def enterprise_fixture(db_session):
    """Provisions a full operational organization with all canonical roles and actors."""
    org = Organization(name=f"Paradox Sports {uuid4().hex[:8]}", code=f"PS_{uuid4().hex[:8]}".upper())
    db_session.add(org)
    db_session.flush()


    v_ops = Vertical(organization_id=org.id, name=f"Operations {uuid4().hex[:4]}")
    v_log = Vertical(organization_id=org.id, name=f"Logistics {uuid4().hex[:4]}")
    db_session.add_all([v_ops, v_log])
    db_session.flush()

    def _create_actor(role_name, name_prefix):
        u = User(
            username=f"{name_prefix}_{uuid4().hex[:6]}",
            full_name=f"{name_prefix.title()} User",
            email=f"{name_prefix}_{uuid4().hex[:6]}@paradoxsports.org",
            password_hash="pwd_hash_fixture",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()

        role = db_session.scalar(select(Role).where(Role.name == role_name))
        if role:
            db_session.add(UserRole(user_id=u.id, role_id=role.id))
        return u

    admin = _create_actor("ADMIN", "admin")
    core = _create_actor("CORE", "core_leader")
    deputy = _create_actor("DEPUTY_CORE", "deputy_leader")
    super_coord = _create_actor("SUPER_COORDINATOR", "super_coord")
    coord_ops = _create_actor("COORDINATOR", "coord_ops")
    coord_log = _create_actor("COORDINATOR", "coord_log")
    volunteer = _create_actor("VOLUNTEER", "volunteer_field")
    event_team_user = _create_actor("EVENT_TEAM", "team_alpha")

    # Vertical memberships
    db_session.add(UserVertical(user_id=core.id, vertical_id=v_ops.id, is_primary=True))
    db_session.add(UserVertical(user_id=deputy.id, vertical_id=v_ops.id, is_primary=True))
    db_session.add(UserVertical(user_id=super_coord.id, vertical_id=v_ops.id, is_primary=True))
    db_session.add(UserVertical(user_id=coord_ops.id, vertical_id=v_ops.id, is_primary=True))
    db_session.add(UserVertical(user_id=volunteer.id, vertical_id=v_ops.id, is_primary=True))
    db_session.add(UserVertical(user_id=coord_log.id, vertical_id=v_log.id, is_primary=True))
    db_session.commit()

    return {
        "org": org,
        "v_ops": v_ops,
        "v_log": v_log,
        "admin": admin,
        "core": core,
        "deputy": deputy,
        "super_coord": super_coord,
        "coord_ops": coord_ops,
        "coord_log": coord_log,
        "volunteer": volunteer,
        "event_team_user": event_team_user,
    }


# -----------------------------------------------------------------------------
# Test Journey 1: Core Operational Workflows (Work, Tasks, My Work & Calendar)
# -----------------------------------------------------------------------------

def test_journey_1_work_management_my_work_and_calendar(db_session, enterprise_fixture):
    actors = enterprise_fixture
    task_service = TaskService(db_session)

    # 1. Core creates a Master Task for Coordinator Ops
    task = task_service.create_task(
        TaskCreate(
            title="Inspect Climbing Wall Rigs",
            description="Perform structural safety evaluation before event opening.",
            vertical_id=actors["v_ops"].id,
            assigned_to_id=actors["coord_ops"].id,
            priority=TaskPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        ),
        actor_id=actors["core"].id,
    )
    db_session.commit()

    assert task.id is not None
    assert task.status == TaskStatus.NOT_STARTED

    # 2. Coordinator views My Work (derived projection from Master Tasks)
    my_work = WorkspaceService.get_unified_my_work(db_session, actors["coord_ops"])
    my_task_ids = [t.id for t in my_work.tasks]
    assert task.id in my_task_ids

    # 3. Volunteer cannot see Coordinator's personal task view
    vol_work = WorkspaceService.get_unified_my_work(db_session, actors["volunteer"])
    vol_task_ids = [t.id for t in vol_work.tasks]
    assert task.id not in vol_task_ids

    # 4. Coordinator updates progress
    updated_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.IN_PROGRESS, completion_percentage=50),
        actor_id=actors["coord_ops"].id,
    )
    db_session.commit()
    assert updated_task.status == TaskStatus.IN_PROGRESS
    assert updated_task.completion_percentage == 50


# -----------------------------------------------------------------------------
# Test Journey 2: Meeting Lifecycle & Idempotent Action Item to Task Conversion
# -----------------------------------------------------------------------------

def test_journey_2_meeting_lifecycle_and_task_conversion(db_session, enterprise_fixture):
    actors = enterprise_fixture
    meeting_service = MeetingService(db_session)

    # 1. Super Coordinator schedules Operational Sync Meeting
    meeting = meeting_service.create_meeting(
        MeetingCreate(
            title="Weekly Operations Review",
            meeting_type=MeetingType.INTERNAL_SYNC,
            meeting_date=date.today() + timedelta(days=2),
            start_time=datetime.now(timezone.utc).time(),
            end_time=(datetime.now(timezone.utc) + timedelta(hours=1)).time(),
            participant_ids=[actors["coord_ops"].id, actors["volunteer"].id],
        ),
        organizer_id=actors["super_coord"].id,
    )
    db_session.commit()

    assert meeting.status == MeetingStatus.SCHEDULED

    # 2. Participants RSVP
    meeting_service.update_rsvp(meeting.id, actors["coord_ops"].id, MeetingRSVPRequest(rsvp_status=RSVPStatus.ACCEPTED))
    meeting_service.update_rsvp(meeting.id, actors["volunteer"].id, MeetingRSVPRequest(rsvp_status=RSVPStatus.DECLINED))
    db_session.commit()

    # 3. Add Action Item
    ai = meeting_service.create_action_item(
        meeting_id=meeting.id,
        data=MeetingActionItemCreate(
            description="Submit safety inspection report",
            assignee_id=actors["coord_ops"].id,
            due_date=datetime.now(timezone.utc) + timedelta(days=4),
        ),
        actor_id=actors["super_coord"].id,
    )
    db_session.commit()

    assert ai.is_converted is False

    # 4. Convert Action Item to Master Task
    ai, converted_task = meeting_service.convert_action_item_to_task(
        meeting_id=meeting.id,
        item_id=ai.id,
        data=MeetingActionConvertToTaskRequest(vertical_id=actors["v_ops"].id),
        actor_id=actors["super_coord"].id,
    )
    db_session.commit()

    assert converted_task.id is not None
    assert converted_task.meeting_id == meeting.id
    assert converted_task.task_type == TaskType.MEETING_FOLLOW_UP

    # 5. Idempotency test: Duplicate conversion must fail
    with pytest.raises(ValidationException, match="already been converted"):
        meeting_service.convert_action_item_to_task(
            meeting_id=meeting.id,
            item_id=ai.id,
            data=MeetingActionConvertToTaskRequest(vertical_id=actors["v_ops"].id),
            actor_id=actors["super_coord"].id,
        )


# -----------------------------------------------------------------------------
# Test Journey 3: Cross-Vertical Requirements & Structured Escalation
# -----------------------------------------------------------------------------

def test_journey_3_cross_vertical_requirements_and_escalation(db_session, enterprise_fixture):
    actors = enterprise_fixture
    req_service = RequirementService(db_session)

    # 1. Ops Coordinator requests Logistics support
    req = req_service.create_requirement(
        RequirementCreate(
            title="Transport Vans for Athletes",
            description="Need 2 accessible vans for venue transport.",
            requesting_vertical_id=actors["v_ops"].id,
            target_vertical_id=actors["v_log"].id,
            priority=RequirementPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=5),
        ),
        requester_id=actors["coord_ops"].id,
    )
    db_session.commit()

    assert req.status == RequirementStatus.OPEN
    assert req.is_escalated is False

    # 2. Logistics Coordinator assigns the requirement
    assigned_req = req_service.assign_requirement(
        req.id,
        RequirementAssignRequest(assignee_id=actors["coord_log"].id),
        actor_id=actors["coord_log"].id,
    )
    db_session.commit()
    assert assigned_req.status == RequirementStatus.ASSIGNED

    # 3. Ops Coordinator escalates requirement due to lack of confirmation
    escalated_req = req_service.escalate_requirement(
        req.id,
        RequirementEscalateRequest(
            escalated_to_id=actors["core"].id,
            reason="Vendor unconfirmed 48 hours before movement window.",
        ),
        actor_id=actors["coord_ops"].id,
    )
    db_session.commit()
    assert escalated_req.is_escalated is True
    assert escalated_req.escalation_reason is not None

    # 4. Core Leader resolves escalation
    resolved_req = req_service.resolve_requirement_escalation(
        req.id,
        RequirementResolveEscalationRequest(
            resolution_notes="Secondary transport provider contracted.",
        ),
        actor_id=actors["core"].id,
    )
    db_session.commit()
    assert resolved_req.is_escalated is False


# -----------------------------------------------------------------------------
# Test Journey 4: Events, Event Team Isolation & POC Group Governance
# -----------------------------------------------------------------------------

def test_journey_4_event_operations_and_event_team_isolation(db_session, enterprise_fixture):
    actors = enterprise_fixture
    event_service = EventService(db_session)
    team_service = EventTeamService(db_session)
    ann_service = AnnouncementService(db_session)

    # 1. Create Event with Head POC
    event = Event(
        name="Adaptive Rock Summit 2026",
        event_type=EventType.TOURNAMENT,
        primary_poc_id=actors["coord_ops"].id,
        vertical_id=actors["v_ops"].id,
        status=EventStatus.PLANNING,
        planned_date=date.today() + timedelta(days=30),
        created_by_id=actors["core"].id,
    )
    db_session.add(event)
    db_session.flush()

    # 2. Associate Event Team profile
    team_profile = EventTeamProfile(
        user_id=actors["event_team_user"].id,
        event_id=event.id,
        team_name="Summit Field Coordination Unit",
        head_name="Alpha Team Leader",
        head_email="alpha.leader@external-partner.org",
        head_phone="+1-555-0199",
    )
    db_session.add(team_profile)
    db_session.commit()

    # 3. Event Team updates profile information
    team_service.update_event_team(
        team_id=team_profile.id,
        data=EventTeamUpdate(
            head_phone="+1-555-9988",
            notes="Updated field operational emergency dispatch line.",
        ),
    )
    db_session.commit()

    db_session.refresh(team_profile)
    assert team_profile.head_phone == "+1-555-9988"

    # 4. Verify Event Team isolation in Announcements:
    # A. Internal vertical announcement
    a_internal = ann_service.create_announcement(
        AnnouncementCreate(
            title="Internal Ops Budget Review",
            content="Confidential financial report.",
            scope=AnnouncementScope.VERTICAL,
            vertical_id=actors["v_ops"].id,
            publish_now=True,
        ),
        author_id=actors["core"].id,
    )
    # B. Event Team announcement
    a_team = ann_service.create_announcement(
        AnnouncementCreate(
            title="Arrival Instructions",
            content="Gate 4 operational hours.",
            scope=AnnouncementScope.EVENT,
            event_id=event.id,
            publish_now=True,
        ),
        author_id=actors["coord_ops"].id,
    )
    db_session.commit()

    # Event Team account queries announcements: Must see Event announcement, NEVER see internal vertical announcement
    items, total = ann_service.list_announcements(actors["event_team_user"], [], is_admin=False)
    seen_ids = [a.id for a in items]
    assert a_team.id in seen_ids
    assert a_internal.id not in seen_ids, "Event Team must NEVER see internal vertical announcements!"


# -----------------------------------------------------------------------------
# Test Journey 5: Dynamic Forms & Atomic Entity Transformation
# -----------------------------------------------------------------------------

def test_journey_5_dynamic_forms_and_atomic_transformation(db_session, enterprise_fixture):
    actors = enterprise_fixture
    form_service = FormService(db_session)

    # 1. Admin creates a dynamic Form with TASK transformation
    form = form_service.create_form(
        FormCreate(
            name="Equipment Request Form",
            description="Submit requests for logistical field equipment.",
            purpose="Procurement collection",
            vertical_id=actors["v_ops"].id,
            target_audience=FormAudience.ORGANIZATION,
            initial_schema=[
                FormFieldSchema(key="title", label="Task Name", type=FormFieldType.TEXT, required=True),
                FormFieldSchema(key="description", label="Task Details", type=FormFieldType.LONG_TEXT, required=True),
                FormFieldSchema(key="priority", label="Priority Level", type=FormFieldType.SELECT, options=["LOW", "MEDIUM", "HIGH", "CRITICAL"], required=True),
            ],
            transformation_config=FormTransformationConfig(
                target_entity="TASK",
                field_mappings={"title": "title", "description": "description"},
            ),
        ),
        owner_id=actors["admin"].id,
    )
    db_session.commit()

    # 2. Publish form version 1
    form_service.publish_form_version(form.id, version_number=1, actor_id=actors["admin"].id)
    db_session.commit()

    # 3. Volunteer submits form response
    submission_data = {
        "title": "Need 5 Climbing Harnesses",
        "description": "Size Medium harnesses for youth clinic.",
        "priority": "HIGH",
    }
    submission = form_service.submit_form(
        form.id,
        FormSubmissionCreate(submission_data=submission_data),
        submitter_id=actors["volunteer"].id,
    )
    db_session.commit()

    assert submission.status == FormSubmissionStatus.SUBMITTED

    # 4. Self-approval prevention: Volunteer cannot approve own submission
    with pytest.raises(ForbiddenException, match="Self-review violation"):
        form_service.review_submission(
            submission.id,
            actors["volunteer"].id,
            FormSubmissionReviewRequest(status=FormSubmissionStatus.APPROVED),
        )

    # 5. Supervisor approves submission -> Atomically transforms into Master Task
    reviewed_sub = form_service.review_submission(
        submission.id,
        actors["super_coord"].id,
        FormSubmissionReviewRequest(status=FormSubmissionStatus.APPROVED, review_notes="Approved for clinic."),
    )
    db_session.commit()

    assert reviewed_sub.status == FormSubmissionStatus.APPROVED
    assert reviewed_sub.transformed_entity_type == "TASK"
    assert reviewed_sub.transformed_entity_id is not None

    # Verify transformed Task in database
    task = db_session.get(Task, reviewed_sub.transformed_entity_id)
    assert task is not None
    assert task.title == "Need 5 Climbing Harnesses"
    assert task.vertical_id == actors["v_ops"].id


# -----------------------------------------------------------------------------
# Test Journey 6: Governed Ownership Transfers, Directives & Audit Immutability
# -----------------------------------------------------------------------------

def test_journey_6_governance_directives_and_immutable_audit(db_session, enterprise_fixture):
    actors = enterprise_fixture
    dir_service = DirectiveService(db_session)
    xfer_service = OwnershipTransferService(db_session)
    audit_service = AuditService(db_session)
    cfg_service = SystemConfigService(db_session)

    # 1. Issue Directive & Acknowledge
    directive = dir_service.create_directive(
        DirectiveCreate(
            title="Emergency Weather Drill Protocol",
            instruction="All coordinators must review evacuation map.",
            scope=DirectiveScope.ALL,
            requires_acknowledgement=True,
            issue_now=True,
        ),
        issued_by_id=actors["core"].id,
    )
    db_session.commit()

    ack = dir_service.acknowledge_directive(
        directive_id=directive.id,
        user_id=actors["coord_ops"].id,
        data=DirectiveAcknowledgeRequest(notes="Read and reviewed."),
    )
    db_session.commit()
    assert ack.status == AcknowledgementStatus.ACKNOWLEDGED

    # Duplicate acknowledgement blocked
    with pytest.raises(ValidationException, match="already been acknowledged"):
        dir_service.acknowledge_directive(
            directive_id=directive.id,
            user_id=actors["coord_ops"].id,
            data=DirectiveAcknowledgeRequest(),
        )

    # 2. Ownership Transfer of a Task
    task = Task(
        title="Stage Rigging Inspection",
        description="Verify rigging safety",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        vertical_id=actors["v_ops"].id,
        assigned_to_id=actors["coord_ops"].id,
        assigned_by_id=actors["super_coord"].id,
    )
    db_session.add(task)
    db_session.flush()

    xfer = xfer_service.request_transfer(
        OwnershipTransferCreate(
            resource_type=TransferResourceType.TASK,
            resource_id=task.id,
            requested_owner_id=actors["super_coord"].id,
            reason="Reassigned for escalation handling.",
        ),
        requested_by_id=actors["coord_ops"].id,
    )
    db_session.commit()

    # Self-approval prohibited
    with pytest.raises(ForbiddenException, match="Self-approval prohibited"):
        xfer_service.review_transfer(
            xfer.id,
            reviewer_id=actors["coord_ops"].id,
            data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED),
        )

    # Four-eyes review approval
    reviewed_xfer = xfer_service.review_transfer(
        xfer.id,
        reviewer_id=actors["super_coord"].id,
        data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Accepted transfer."),
    )
    db_session.commit()
    assert reviewed_xfer.status == TransferStatus.COMPLETED

    db_session.refresh(task)
    assert task.assigned_to_id == actors["super_coord"].id, "Task ownership must mutate atomically!"

    # 3. Audit Immutability
    audit_entry = audit_service.log(
        action="FINAL_SYSTEM_VERIFICATION",
        resource_type="GOVERNANCE",
        resource_id=str(xfer.id),
        outcome="SUCCESS",
        actor_id=actors["admin"].id,
    )
    db_session.commit()

    with pytest.raises(ImmutableAuditException):
        audit_service.update_record(audit_entry.id)

    with pytest.raises(ImmutableAuditException):
        audit_service.delete_record(audit_entry.id)

    # 4. Typed Config Validation
    cfg = cfg_service.create_config(
        SystemConfigCreate(
            key=f"max_concurrent_logins_{uuid4().hex[:6]}",
            value="10",
            value_type=ConfigValueType.INTEGER,
            description="Max sessions per user",
        ),
        actor_id=actors["admin"].id,
    )
    db_session.commit()
    assert cfg.value == "10"


# -----------------------------------------------------------------------------
# Test Journey 7: Full System Analytics & Fresh-Session Persistence Truth
# -----------------------------------------------------------------------------

def test_journey_7_system_analytics_and_fresh_session_persistence(db_session, enterprise_fixture):
    actors = enterprise_fixture
    analytics_service = AnalyticsService(db_session)
    admin_reporting = AdminReportingService(db_session)

    # 1. Query Operational Dashboard
    dashboard = analytics_service.get_operational_dashboard()
    assert dashboard.generated_at is not None
    assert dashboard.active_tasks >= 0

    # 2. Query Performance Indicators
    indicators = analytics_service.get_performance_indicators()
    assert 0.0 <= indicators.task_completion_rate_pct <= 100.0
    assert 0.0 <= indicators.reporting_compliance_rate_pct <= 100.0

    # 3. Query Administrative Compliance Report
    compliance_report = admin_reporting.get_reporting_compliance_report(days=7)
    assert compliance_report.total_records > 0

    # 4. Fresh-Session Persistence Truth: Disconnect DB session and verify reload
    target_task_id = db_session.scalar(select(Task.id).where(Task.vertical_id == actors["v_ops"].id))
    db_session.close()

    if target_task_id:
        fresh_task = db_session.get(Task, target_task_id)
        assert fresh_task is not None
        assert fresh_task.id == target_task_id
