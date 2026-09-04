"""
Phase 5 Comprehensive Acceptance Test Suite: Communication + Governance + Analytics
Verifies all Phase 5 specifications:
1. Announcement Audience Scoping & Event Team Isolation
2. Directive Issuance, Acknowledgement & Duplicate Prevention
3. Notification Server-Authoritative Ownership Isolation
4. Communication Tracker & Vertical/Event Linkage
5. Governed Ownership Transfers with Four-Eyes Validation
6. Append-Only Immutable Audit Center (ImmutableAuditException)
7. Typed System Configuration Management
8. Operational Intelligence, Dashboards & Performance Indicators with Exact Metrics
9. Fresh-Session PostgreSQL Persistence
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
from app.models.governance import ConfigValueType, OwnershipTransfer, SystemConfig, TransferResourceType, TransferStatus
from app.models.issue import Issue, IssueSensitivity, IssueStatus
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, MeetingType, RSVPStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.report import DailyReportStatus, DailyWorkReport
from app.models.requirement import Requirement, RequirementPriority, RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import AccountStatus, User
from app.schemas.communication import (
    AnnouncementCreate,
    AnnouncementUpdate,
    CommunicationLogCreate,
    DirectiveAcknowledgeRequest,
    DirectiveCreate,
)
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest, SystemConfigCreate, SystemConfigUpdate
from app.services.admin_reporting_service import AdminReportingService
from app.services.analytics_service import AnalyticsService
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService
from app.services.communication_service import CommunicationLogService
from app.services.config_service import SystemConfigService
from app.services.directive_service import DirectiveService
from app.services.notification_service import NotificationService
from app.services.transfer_service import OwnershipTransferService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def org_and_verticals(db_session):
    org = Organization(name=f"Org {uuid4().hex[:6]}", code=f"ORG_{uuid4().hex[:4]}".upper())
    db_session.add(org)
    db_session.flush()

    v1 = Vertical(organization_id=org.id, name=f"Vertical Alpha {uuid4().hex[:4]}")
    v2 = Vertical(organization_id=org.id, name=f"Vertical Beta {uuid4().hex[:4]}")
    db_session.add_all([v1, v2])
    db_session.flush()
    return org, v1, v2


@pytest.fixture
def team_users(db_session, org_and_verticals):
    org, v1, v2 = org_and_verticals

    def _create_user(name_prefix):
        u = User(
            username=f"{name_prefix}_{uuid4().hex[:6]}",
            full_name=f"{name_prefix.title()} User",
            email=f"{name_prefix}_{uuid4().hex[:6]}@example.com",
            password_hash="hashed_pwd_stub",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()
        return u

    admin = _create_user("admin")
    coord1 = _create_user("coord1")
    coord2 = _create_user("coord2")
    event_team_user = _create_user("event_team")

    # Assign Verticals
    db_session.add(UserVertical(user_id=coord1.id, vertical_id=v1.id, is_primary=True))
    db_session.add(UserVertical(user_id=coord2.id, vertical_id=v2.id, is_primary=True))
    db_session.add(UserVertical(user_id=admin.id, vertical_id=v1.id, is_primary=True))

    # Assign Roles
    role_admin = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
    role_coord = db_session.scalar(select(Role).where(Role.name == "COORDINATOR"))
    role_evt_team = db_session.scalar(select(Role).where(Role.name == "EVENT_TEAM"))

    if role_admin:
        db_session.add(UserRole(user_id=admin.id, role_id=role_admin.id))
    if role_coord:
        db_session.add(UserRole(user_id=coord1.id, role_id=role_coord.id))
        db_session.add(UserRole(user_id=coord2.id, role_id=role_coord.id))
    if role_evt_team:
        db_session.add(UserRole(user_id=event_team_user.id, role_id=role_evt_team.id))

    db_session.flush()
    return admin, coord1, coord2, event_team_user


# -----------------------------------------------------------------------------
# Part A: Announcements & Audience Isolation
# -----------------------------------------------------------------------------

def test_announcement_scoping_and_audience_isolation(db_session, org_and_verticals, team_users):
    org, v1, v2 = org_and_verticals
    admin, coord1, coord2, event_team_user = team_users
    ann_service = AnnouncementService(db_session)

    # 1. Create an Event and Event Team profile
    evt = Event(
        name=f"Summit {uuid4().hex[:6]}",
        event_type=EventType.TOURNAMENT,
        primary_poc_id=coord1.id,
        vertical_id=v1.id,
        status=EventStatus.IN_PROGRESS,
        planned_date=date.today() + timedelta(days=10),
        created_by_id=admin.id,
    )
    db_session.add(evt)
    db_session.flush()

    db_session.add(EventTeamProfile(user_id=event_team_user.id, event_id=evt.id, team_name="Alpha Summit Team"))
    db_session.flush()

    # 2. Publish Org-wide Announcement
    a_all = ann_service.create_announcement(
        AnnouncementCreate(
            title="General Policy Update",
            content="Welcome to all organization staff.",
            scope=AnnouncementScope.ALL,
            publish_now=True,
        ),
        author_id=admin.id,
    )

    # 3. Publish Vertical Alpha Announcement
    a_v1 = ann_service.create_announcement(
        AnnouncementCreate(
            title="Alpha Operations Briefing",
            content="Confidential briefing for Vertical Alpha only.",
            scope=AnnouncementScope.VERTICAL,
            vertical_id=v1.id,
            publish_now=True,
        ),
        author_id=admin.id,
    )

    # 4. Publish Event Announcement
    a_evt = ann_service.create_announcement(
        AnnouncementCreate(
            title="Summit Operational Protocol",
            content="Event specific instructions for Summit.",
            scope=AnnouncementScope.EVENT,
            event_id=evt.id,
            publish_now=True,
        ),
        author_id=coord1.id,
    )
    db_session.commit()

    # 5. Verify Coord 1 (in V1) visibility
    items_c1, tot_c1 = ann_service.list_announcements(coord1, [v1.id], is_admin=False)
    ids_c1 = [a.id for a in items_c1]
    assert a_all.id in ids_c1
    assert a_v1.id in ids_c1
    assert a_evt.id in ids_c1

    # 6. Verify Coord 2 (in V2) visibility (Cannot see V1 announcement)
    items_c2, tot_c2 = ann_service.list_announcements(coord2, [v2.id], is_admin=False)
    ids_c2 = [a.id for a in items_c2]
    assert a_all.id in ids_c2
    assert a_v1.id not in ids_c2  # V1 is isolated!

    # 7. Verify Event Team User visibility (Never sees internal Vertical announcements)
    items_evt, tot_evt = ann_service.list_announcements(event_team_user, [], is_admin=False)
    ids_evt = [a.id for a in items_evt]
    assert a_all.id in ids_evt
    assert a_evt.id in ids_evt
    assert a_v1.id not in ids_evt  # Event Team isolated from internal vertical comms!


# -----------------------------------------------------------------------------
# Part B: Directives & Acknowledgement Control
# -----------------------------------------------------------------------------

def test_directive_acknowledgement_and_duplicate_prevention(db_session, team_users):
    admin, coord1, coord2, _ = team_users
    dir_service = DirectiveService(db_session)

    # 1. Issue a Directive to ALL
    d = dir_service.create_directive(
        DirectiveCreate(
            title="Q3 Safety Protocol",
            instruction="All coordinators must complete safety checklist by Friday.",
            scope=DirectiveScope.ALL,
            requires_acknowledgement=True,
            issue_now=True,
        ),
        issued_by_id=admin.id,
    )
    db_session.commit()

    assert d.status == DirectiveStatus.ISSUED

    # 2. Coord 1 acknowledges
    ack1 = dir_service.acknowledge_directive(
        directive_id=d.id,
        user_id=coord1.id,
        data=DirectiveAcknowledgeRequest(notes="Read and reviewed with my team."),
    )
    db_session.commit()

    assert ack1.status == AcknowledgementStatus.ACKNOWLEDGED
    assert ack1.notes == "Read and reviewed with my team."
    assert ack1.acknowledged_at is not None

    # 3. Duplicate acknowledgement by Coord 1 must be rejected
    with pytest.raises(ValidationException, match="already been acknowledged"):
        dir_service.acknowledge_directive(
            directive_id=d.id,
            user_id=coord1.id,
            data=DirectiveAcknowledgeRequest(notes="Attempting duplicate"),
        )

    # 4. Directive with requires_acknowledgement=False cannot be acknowledged
    d_no_ack = dir_service.create_directive(
        DirectiveCreate(
            title="Info Only Directive",
            instruction="Informational note.",
            scope=DirectiveScope.ALL,
            requires_acknowledgement=False,
            issue_now=True,
        ),
        issued_by_id=admin.id,
    )
    db_session.commit()

    with pytest.raises(ValidationException, match="does not require acknowledgement"):
        dir_service.acknowledge_directive(
            directive_id=d_no_ack.id,
            user_id=coord2.id,
            data=DirectiveAcknowledgeRequest(),
        )


# -----------------------------------------------------------------------------
# Part C: Notifications & Recipient Isolation
# -----------------------------------------------------------------------------

def test_notification_recipient_ownership_isolation(db_session, team_users):
    admin, coord1, coord2, _ = team_users
    notif_service = NotificationService(db_session)

    # Create notifications
    n1 = notif_service.create_notification(
        recipient_id=coord1.id,
        title="Personal Task Assignment",
        message="You have a new task assigned.",
        notification_type=NotificationType.TASK,
    )
    n2 = notif_service.create_notification(
        recipient_id=coord2.id,
        title="Escalation Alert",
        message="Critical requirement escalated.",
        notification_type=NotificationType.REQUIREMENT,
    )
    db_session.commit()

    # 1. Coord 1 marks own notification as read
    read_n1 = notif_service.mark_as_read(n1.id, user_id=coord1.id)
    assert read_n1.read_status == NotificationReadStatus.READ

    # 2. Coord 1 attempting to read or dismiss Coord 2's notification must FAIL
    with pytest.raises(ForbiddenException, match="cannot access notifications belonging to another user"):
        notif_service.mark_as_read(n2.id, user_id=coord1.id)

    with pytest.raises(ForbiddenException, match="cannot access notifications belonging to another user"):
        notif_service.dismiss_notification(n2.id, user_id=coord1.id)


# -----------------------------------------------------------------------------
# Part D: Communication Tracker & Event Linkage
# -----------------------------------------------------------------------------

def test_communication_tracker_and_event_linkage(db_session, org_and_verticals, team_users):
    org, v1, _ = org_and_verticals
    admin, coord1, _, _ = team_users
    comm_service = CommunicationLogService(db_session)

    evt = Event(
        name=f"Regional Invitational {uuid4().hex[:6]}",
        event_type=EventType.MATCH,
        primary_poc_id=coord1.id,
        vertical_id=v1.id,
        status=EventStatus.PLANNING,
        planned_date=date.today() + timedelta(days=20),
        created_by_id=admin.id,
    )
    db_session.add(evt)
    db_session.flush()

    # Create official communication record linked to event
    log = comm_service.create_log(
        CommunicationLogCreate(
            communication_type=CommunicationType.OFFICIAL_MESSAGE,
            subject="Venue Security Agreement Confirmation",
            sender_info="Security Director <sec@venue.org>",
            recipient_info="Operations Team <ops@paradoxsports.org>",
            vertical_id=v1.id,
            event_id=evt.id,
            reference_link="https://docs.paradoxsports.org/sec-agreement-2026.pdf",
            remarks="Signed contract received and archived.",
        ),
        created_by_id=coord1.id,
    )
    db_session.commit()

    assert log.id is not None
    assert log.event_id == evt.id
    assert log.vertical_id == v1.id

    # Filter logs by event
    items, total = comm_service.list_logs(event_id=evt.id)
    assert total >= 1
    assert any(item.id == log.id for item in items)


# -----------------------------------------------------------------------------
# Part E: Governance & Governed Ownership Transfers
# -----------------------------------------------------------------------------

def test_governed_ownership_transfer_with_four_eyes_approval(db_session, org_and_verticals, team_users):
    org, v1, _ = org_and_verticals
    admin, coord1, coord2, _ = team_users
    transfer_service = OwnershipTransferService(db_session)

    # 1. Create a task assigned to Coord 1
    task = Task(
        title="Inspect Stage Equipment",
        description="Verify rigging safety",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        vertical_id=v1.id,
        assigned_to_id=coord1.id,
        assigned_by_id=coord1.id,
    )
    db_session.add(task)
    db_session.flush()

    # 2. Coord 1 requests transfer of ownership to Admin (in V1)
    transfer = transfer_service.request_transfer(
        OwnershipTransferCreate(
            resource_type=TransferResourceType.TASK,
            resource_id=task.id,
            requested_owner_id=admin.id,
            reason="Reassigned due to scheduling conflict.",
        ),
        requested_by_id=coord1.id,
    )
    db_session.commit()

    assert transfer.status == TransferStatus.PENDING

    # 3. Self-approval prohibition: Coord 1 cannot approve their own transfer
    with pytest.raises(ForbiddenException, match="Self-approval prohibited"):
        transfer_service.review_transfer(
            transfer_id=transfer.id,
            reviewer_id=coord1.id,
            data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED),
        )

    # 4. Four-eyes review: Admin approves the transfer
    reviewed = transfer_service.review_transfer(
        transfer_id=transfer.id,
        reviewer_id=admin.id,
        data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Approved handover."),
    )
    db_session.commit()

    assert reviewed.status == TransferStatus.COMPLETED
    assert reviewed.completed_at is not None

    # Verify task ownership was mutated transactionally
    db_session.refresh(task)
    assert task.assigned_to_id == admin.id


# -----------------------------------------------------------------------------
# Part F: Immutable Audit Center
# -----------------------------------------------------------------------------

def test_audit_center_immutability(db_session, team_users):
    admin, coord1, _, _ = team_users
    audit_service = AuditService(db_session)

    # 1. Append log
    entry = audit_service.log(
        action="GOVERNANCE_CONFIG_CHANGE",
        resource_type="SYSTEM_CONFIG",
        resource_id="max_login_attempts",
        outcome="SUCCESS",
        actor_id=admin.id,
        details={"old_value": "5", "new_value": "3"},
    )
    db_session.commit()

    assert entry.id is not None

    # 2. Immutability verification: Updates and Deletions must throw ImmutableAuditException
    with pytest.raises(ImmutableAuditException):
        audit_service.update_record(entry.id, {"outcome": "FAILURE"})

    with pytest.raises(ImmutableAuditException):
        audit_service.delete_record(entry.id)


# -----------------------------------------------------------------------------
# Part G: Typed System Configuration
# -----------------------------------------------------------------------------

def test_typed_system_configuration(db_session, team_users):
    admin, _, _, _ = team_users
    config_service = SystemConfigService(db_session)

    key_int = f"max_active_tasks_{uuid4().hex[:6]}"
    key_bool = f"allow_self_registration_{uuid4().hex[:6]}"

    # 1. Valid INTEGER config
    c_int = config_service.create_config(
        SystemConfigCreate(
            key=key_int,
            value="25",
            value_type=ConfigValueType.INTEGER,
            description="Max tasks per operator",
        ),
        actor_id=admin.id,
    )
    db_session.commit()
    assert c_int.value == "25"

    # 2. Invalid INTEGER config must fail validation
    with pytest.raises(ValidationException, match="must be a valid integer"):
        config_service.create_config(
            SystemConfigCreate(
                key=f"invalid_int_{uuid4().hex[:6]}",
                value="not_a_number",
                value_type=ConfigValueType.INTEGER,
            ),
            actor_id=admin.id,
        )

    # 3. Valid BOOLEAN config
    c_bool = config_service.create_config(
        SystemConfigCreate(
            key=key_bool,
            value="true",
            value_type=ConfigValueType.BOOLEAN,
        ),
        actor_id=admin.id,
    )
    db_session.commit()
    assert c_bool.value.lower() == "true"


# -----------------------------------------------------------------------------
# Part H: Operational Intelligence & Performance Indicators Accuracy
# -----------------------------------------------------------------------------

def test_analytics_and_performance_indicators_accuracy(db_session, org_and_verticals, team_users):
    org, v1, _ = org_and_verticals
    admin, coord1, _, _ = team_users
    analytics_service = AnalyticsService(db_session)
    admin_reporting = AdminReportingService(db_session)

    # Clean existing entities to test independent metric calculations
    db_session.query(Task).delete()
    db_session.query(Issue).delete()
    db_session.query(Requirement).delete()
    db_session.query(DailyWorkReport).delete()
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = date.today()

    # 1. Seed Tasks: 3 completed, 1 in-progress (overdue), 1 blocked -> Total 5
    t1 = Task(title="T1", status=TaskStatus.COMPLETED, vertical_id=v1.id, assigned_to_id=coord1.id, assigned_by_id=admin.id)
    t2 = Task(title="T2", status=TaskStatus.COMPLETED, vertical_id=v1.id, assigned_to_id=coord1.id, assigned_by_id=admin.id)
    t3 = Task(title="T3", status=TaskStatus.COMPLETED, vertical_id=v1.id, assigned_to_id=coord1.id, assigned_by_id=admin.id)
    t4 = Task(title="T4", status=TaskStatus.IN_PROGRESS, deadline=now - timedelta(days=2), vertical_id=v1.id, assigned_to_id=coord1.id, assigned_by_id=admin.id)
    t5 = Task(title="T5", status=TaskStatus.BLOCKED, vertical_id=v1.id, assigned_to_id=coord1.id, assigned_by_id=admin.id)
    db_session.add_all([t1, t2, t3, t4, t5])

    # 2. Seed Issues: 2 resolved, 1 escalated -> Total 3
    i1 = Issue(title="I1", description="Desc 1", status=IssueStatus.RESOLVED, sensitivity=IssueSensitivity.NORMAL, vertical_id=v1.id, raised_by_id=coord1.id)
    i2 = Issue(title="I2", description="Desc 2", status=IssueStatus.RESOLVED, sensitivity=IssueSensitivity.NORMAL, vertical_id=v1.id, raised_by_id=coord1.id)
    i3 = Issue(title="I3", description="Desc 3", status=IssueStatus.ESCALATED, sensitivity=IssueSensitivity.CONFIDENTIAL, vertical_id=v1.id, raised_by_id=coord1.id)
    db_session.add_all([i1, i2, i3])

    # 3. Seed Requirements: 2 completed, 1 open (escalated) -> Total 3
    r1 = Requirement(title="R1", description="Req 1", status=RequirementStatus.COMPLETED, requesting_vertical_id=v1.id, target_vertical_id=v1.id, requester_id=coord1.id)
    r2 = Requirement(title="R2", description="Req 2", status=RequirementStatus.COMPLETED, requesting_vertical_id=v1.id, target_vertical_id=v1.id, requester_id=coord1.id)
    r3 = Requirement(title="R3", description="Req 3", status=RequirementStatus.OPEN, is_escalated=True, requesting_vertical_id=v1.id, target_vertical_id=v1.id, requester_id=coord1.id)
    db_session.add_all([r1, r2, r3])

    # 4. Seed Daily Reports: 2 reports submitted for coord1 in last 7 days
    db_session.add(DailyWorkReport(user_id=coord1.id, vertical_id=v1.id, report_date=today, status=DailyReportStatus.REVIEWED, work_summary="Done work", tasks_completed="3 tasks", blockers="None"))
    db_session.add(DailyWorkReport(user_id=coord1.id, vertical_id=v1.id, report_date=today - timedelta(days=1), status=DailyReportStatus.SUBMITTED, work_summary="Done work 2", tasks_completed="2 tasks", blockers="None"))

    db_session.commit()

    # 5. Query Indicators and verify exact mathematical formulas
    indicators = analytics_service.get_performance_indicators()

    # Task Completion Rate: 3 / 5 = 60.0%
    assert indicators.task_completion_rate_pct == 60.0

    # Overdue Task Rate: 1 / 5 = 20.0%
    assert indicators.overdue_task_rate_pct == 20.0

    # Issue Resolution Rate: 2 / 3 = 66.7%
    assert indicators.issue_resolution_rate_pct == 66.7

    # Requirement Resolution Rate: 2 / 3 = 66.7%
    assert indicators.requirement_resolution_rate_pct == 66.7

    # Escalation Rate: (1 esc req + 1 esc issue) / (3 reqs + 3 issues) = 2 / 6 = 33.3%
    assert indicators.escalation_rate_pct == 33.3

    # 6. Verify Dashboard Metrics
    dashboard = analytics_service.get_operational_dashboard()
    assert dashboard.completed_tasks == 3
    assert dashboard.overdue_tasks == 1
    assert dashboard.blocked_tasks == 1
    assert dashboard.escalated_issues == 1

    # 7. Verify Compliance Admin Report
    rep = admin_reporting.get_reporting_compliance_report(days=7)
    assert rep.total_records > 0
    assert "overall_compliance_pct" in rep.summary


# -----------------------------------------------------------------------------
# Part I: Fresh-Session PostgreSQL Persistence Verification
# -----------------------------------------------------------------------------

def test_fresh_session_persistence(db_session, team_users):
    admin, coord1, _, _ = team_users
    ann_service = AnnouncementService(db_session)

    title = f"Persistent Broadcast {uuid4().hex[:6]}"
    ann = ann_service.create_announcement(
        AnnouncementCreate(
            title=title,
            content="Testing persistence across fresh session disconnect/reconnect.",
            scope=AnnouncementScope.ALL,
            publish_now=True,
        ),
        author_id=admin.id,
    )
    ann_id = ann.id
    db_session.commit()

    # Close the current session to force a fresh session reload
    db_session.close()

    # Query in fresh session
    fresh_ann = db_session.get(Announcement, ann_id)
    assert fresh_ann is not None
    assert fresh_ann.title == title
    assert fresh_ann.status == AnnouncementStatus.PUBLISHED
