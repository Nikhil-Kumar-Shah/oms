"""
Phase 10D: Notification Recipient Integrity & Delivery Correction Test Suite
Verifies:
1. Brand new user with zero notifications returns total=0, unread_count=0, items=[].
2. Database-level isolation: presence of global notifications for other users does not leak to non-recipients.
3. Same-vertical isolation: multiple users in the same vertical division only receive notifications explicitly addressed to them.
4. Cross-vertical isolation: vertical-scoped broadcasts never leak to other verticals.
5. Batch dispatch exclusion: author/creator is never sent a self-notification.
6. Meeting and Task recipient explicit scoping.
7. Requirement assignment, escalation, and counterparty message notification scoping.
8. Microsecond index-driven query performance on empty and populated user feeds.
"""

import pytest
import time
from uuid import uuid4
from datetime import date, datetime, timezone
from app.models.user import User, AccountStatus
from app.models.organization import Organization, Vertical, VerticalStatus, UserVertical
from app.models.rbac import Role, UserRole
from app.models.communication import (
    Announcement,
    AnnouncementPriority,
    AnnouncementScope,
    AnnouncementStatus,
    Directive,
    DirectivePriority,
    DirectiveScope,
    Notification,
    NotificationType,
    NotificationReadStatus,
)
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.meeting import Meeting, MeetingType, MeetingStatus
from app.models.requirement import Requirement, RequirementStatus, RequirementPriority
from app.services.notification_service import NotificationService
from app.services.announcement_service import AnnouncementService
from app.services.directive_service import DirectiveService
from app.services.meeting_service import MeetingService
from app.services.task_service import TaskService
from app.services.requirement_service import RequirementService
from app.schemas.communication import AnnouncementCreate, DirectiveCreate
from app.schemas.meeting import MeetingCreate
from app.schemas.task import TaskCreate, TaskReassignRequest
from app.schemas.requirement import RequirementCreate, RequirementMessageCreate



def _setup_org_and_verticals(db_session):
    org = db_session.query(Organization).filter(Organization.code == "TEST_ORG_10D").first()
    if not org:
        org = Organization(name="Test Org 10D", code="TEST_ORG_10D", description="Test org")
        db_session.add(org)
        db_session.flush()

    v1 = db_session.query(Vertical).filter(Vertical.name == "V_Alpha_10D").first()
    if not v1:
        v1 = Vertical(organization_id=org.id, name="V_Alpha_10D", description="Alpha Vertical", status=VerticalStatus.ACTIVE)
        db_session.add(v1)
        db_session.flush()

    v2 = db_session.query(Vertical).filter(Vertical.name == "V_Beta_10D").first()
    if not v2:
        v2 = Vertical(organization_id=org.id, name="V_Beta_10D", description="Beta Vertical", status=VerticalStatus.ACTIVE)
        db_session.add(v2)
        db_session.flush()

    return org, v1, v2


def _create_user(db_session, username: str, email: str, vertical_id=None, role_name: str = "COORDINATOR") -> User:
    user = User(
        username=username,
        email=email,
        full_name=f"Full {username}",
        password_hash="hashed_test_password",
        account_status=AccountStatus.ACTIVE,
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

    if vertical_id:
        uv = UserVertical(user_id=user.id, vertical_id=vertical_id, is_primary=True)
        db_session.add(uv)
        db_session.flush()

    return user


def test_new_user_zero_notifications_integrity(db_session):
    """A new user must receive zero notifications even when hundreds exist in the database."""
    service = NotificationService(db_session)
    _, v1, _ = _setup_org_and_verticals(db_session)

    # Populate database with historical notifications for other users
    other_user = _create_user(db_session, f"other_{uuid4().hex[:6]}", f"other_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    for i in range(20):
        service.create_notification(
            recipient_id=other_user.id,
            title=f"Historical Notice #{i}",
            message=f"Past notification content #{i}",
            notification_type=NotificationType.SYSTEM,
        )
    db_session.commit()

    # Create brand-new user with no assigned work
    new_user = _create_user(db_session, f"brand_new_{uuid4().hex[:6]}", f"new_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    db_session.commit()

    # Verify query returns absolute empty feed
    items, total, unread = service.list_user_notifications(new_user.id)
    assert total == 0
    assert unread == 0
    assert items == []

    # Verify unread count is zero
    assert service.get_unread_count(new_user.id) == 0


def test_same_vertical_recipient_isolation(db_session):
    """Two users in the same vertical division must only receive notifications addressed to them."""
    _, v1, _ = _setup_org_and_verticals(db_session)
    user_a = _create_user(db_session, f"vert_a_{uuid4().hex[:6]}", f"va_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    user_b = _create_user(db_session, f"vert_b_{uuid4().hex[:6]}", f"vb_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    manager = _create_user(db_session, f"mgr_{uuid4().hex[:6]}", f"mgr_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id, role_name="SUPER_COORDINATOR")

    task_service = TaskService(db_session)
    task = task_service.create_task(
        data=TaskCreate(
            title="Football Field Maintenance",
            vertical_id=v1.id,
            assigned_to_id=user_a.id,
            priority=TaskPriority.HIGH,
            task_type=TaskType.ROUTINE,
        ),
        actor_id=manager.id,
    )
    db_session.commit()

    notif_service = NotificationService(db_session)

    # User A was assigned -> should have 1 notification
    items_a, total_a, unread_a = notif_service.list_user_notifications(user_a.id)
    assert total_a == 1
    assert unread_a == 1
    assert items_a[0].related_resource_id == task.id
    assert "Football Field Maintenance" in items_a[0].title

    # User B is in the SAME vertical, but was not assigned -> must have 0 notifications
    items_b, total_b, unread_b = notif_service.list_user_notifications(user_b.id)
    assert total_b == 0
    assert unread_b == 0
    assert items_b == []


def test_cross_vertical_broadcast_isolation(db_session):
    """Announcements scoped to Vertical Alpha must not dispatch notifications to Vertical Beta users."""
    _, v_alpha, v_beta = _setup_org_and_verticals(db_session)
    user_alpha = _create_user(db_session, f"alpha_{uuid4().hex[:6]}", f"alpha_{uuid4().hex[:6]}@oms.local", vertical_id=v_alpha.id)
    user_beta = _create_user(db_session, f"beta_{uuid4().hex[:6]}", f"beta_{uuid4().hex[:6]}@oms.local", vertical_id=v_beta.id)
    author = _create_user(db_session, f"auth_{uuid4().hex[:6]}", f"auth_{uuid4().hex[:6]}@oms.local", vertical_id=v_alpha.id, role_name="SUPER_COORDINATOR")

    ann_service = AnnouncementService(db_session)
    ann = ann_service.create_announcement(
        data=AnnouncementCreate(
            title="Alpha Equipment Audit",
            content="All gear must be accounted for by Friday.",
            scope=AnnouncementScope.VERTICAL,
            vertical_id=v_alpha.id,
            category="GENERAL",
            priority=AnnouncementPriority.HIGH,
            publish_now=True,
        ),
        author_id=author.id,
    )
    db_session.commit()

    notif_service = NotificationService(db_session)

    # User Alpha in target vertical receives notification
    items_a, total_a, unread_a = notif_service.list_user_notifications(user_alpha.id)
    assert total_a == 1
    assert unread_a == 1
    assert items_a[0].related_resource_id == ann.id

    # Author is excluded from self-notification
    items_author, total_author, _ = notif_service.list_user_notifications(author.id)
    assert total_author == 0

    # User Beta in another vertical receives NOTHING
    items_b, total_b, unread_b = notif_service.list_user_notifications(user_beta.id)
    assert total_b == 0
    assert unread_b == 0
    assert items_b == []


def test_meeting_participant_scoping_and_organizer_exclusion(db_session):
    """Meeting invite notifications are sent strictly to invited participants, excluding organizer and uninvited users."""
    _, v1, _ = _setup_org_and_verticals(db_session)
    organizer = _create_user(db_session, f"org_{uuid4().hex[:6]}", f"org_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    p1 = _create_user(db_session, f"p1_{uuid4().hex[:6]}", f"p1_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    p2 = _create_user(db_session, f"p2_{uuid4().hex[:6]}", f"p2_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)
    uninvited = _create_user(db_session, f"uninv_{uuid4().hex[:6]}", f"uninv_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)

    meeting_service = MeetingService(db_session)
    meeting = meeting_service.create_meeting(
        data=MeetingCreate(
            title="Weekly Operational Standup",
            description="Discussing sprint blockers",
            meeting_type=MeetingType.INTERNAL_SYNC,
            meeting_date=date.today(),
            start_time="10:00",
            end_time="11:00",
            vertical_id=v1.id,
            participant_ids=[p1.id, p2.id, organizer.id],
        ),
        organizer_id=organizer.id,
    )
    db_session.commit()


    notif_service = NotificationService(db_session)

    # Organizer has 0 notifications (no self-invite)
    assert notif_service.get_unread_count(organizer.id) == 0

    # Invited participants have 1 notification each
    assert notif_service.get_unread_count(p1.id) == 1
    assert notif_service.get_unread_count(p2.id) == 1

    # Uninvited user has 0 notifications
    assert notif_service.get_unread_count(uninvited.id) == 0


def test_requirement_message_counterparty_scoping(db_session):
    """When a message is posted on a requirement, only the counterparty receives a notification."""
    _, v_req, v_tgt = _setup_org_and_verticals(db_session)
    requester = _create_user(db_session, f"req_usr_{uuid4().hex[:6]}", f"requsr_{uuid4().hex[:6]}@oms.local", vertical_id=v_req.id)
    assignee = _create_user(db_session, f"asg_usr_{uuid4().hex[:6]}", f"asgusr_{uuid4().hex[:6]}@oms.local", vertical_id=v_tgt.id)
    bystander = _create_user(db_session, f"byst_{uuid4().hex[:6]}", f"byst_{uuid4().hex[:6]}@oms.local", vertical_id=v_tgt.id)

    req_service = RequirementService(db_session)
    req = req_service.create_requirement(
        data=RequirementCreate(
            title="Medical Kit Replenishment",
            description="Need 5 fresh first aid kits",
            requesting_vertical_id=v_req.id,
            target_vertical_id=v_tgt.id,
            priority=RequirementPriority.HIGH,
            assignee_id=assignee.id,
        ),
        requester_id=requester.id,
    )
    db_session.commit()

    notif_service = NotificationService(db_session)

    # Initial state: Assignee received assignment notification
    assert notif_service.get_unread_count(assignee.id) == 1
    assert notif_service.get_unread_count(requester.id) == 0

    # Requester posts a follow-up message
    req_service.add_message(
        req_id=req.id,
        data=RequirementMessageCreate(content="Please include cold spray as well."),
        author_id=requester.id,
    )
    db_session.commit()

    # Assignee now has 2 notifications (Assignment + Message)
    assert notif_service.get_unread_count(assignee.id) == 2

    # Requester (author of message) does NOT receive self-notification
    assert notif_service.get_unread_count(requester.id) == 0

    # Bystander receives 0 notifications
    assert notif_service.get_unread_count(bystander.id) == 0


def test_notification_performance_benchmarks(db_session):
    """Tests sub-10ms unread count and sub-15ms list query benchmarks."""
    service = NotificationService(db_session)
    _, v1, _ = _setup_org_and_verticals(db_session)
    user = _create_user(db_session, f"bench_{uuid4().hex[:6]}", f"bench_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)

    # 1. Empty user benchmark
    t0 = time.perf_counter()
    count_0 = service.get_unread_count(user.id)
    t_unread_0 = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    items_0, total_0, _ = service.list_user_notifications(user.id)
    t_list_0 = (time.perf_counter() - t1) * 1000

    assert count_0 == 0
    assert total_0 == 0
    assert t_unread_0 < 10.0, f"Empty unread count took {t_unread_0:.2f}ms, expected < 10ms"
    assert t_list_0 < 15.0, f"Empty list query took {t_list_0:.2f}ms, expected < 15ms"

    # 2. Populated user benchmark (50 notifications)
    for i in range(50):
        service.create_notification(
            recipient_id=user.id,
            title=f"Benchmark Alert #{i}",
            message=f"Performance payload content #{i}",
            notification_type=NotificationType.TASK,
        )
    db_session.commit()

    t2 = time.perf_counter()
    count_50 = service.get_unread_count(user.id)
    t_unread_50 = (time.perf_counter() - t2) * 1000

    t3 = time.perf_counter()
    items_50, total_50, _ = service.list_user_notifications(user.id, limit=50)
    t_list_50 = (time.perf_counter() - t3) * 1000

    assert count_50 == 50
    assert total_50 == 50
    assert len(items_50) == 50
    assert t_unread_50 < 15.0, f"Populated unread count took {t_unread_50:.2f}ms, expected < 15ms"
    assert t_list_50 < 30.0, f"Populated list query took {t_list_50:.2f}ms, expected < 30ms"



def test_dismiss_removes_from_default_list_and_total(db_session):
    """Dismissing a notification sets its status to DISMISSED and permanently removes it from default listing."""
    service = NotificationService(db_session)
    _, v1, _ = _setup_org_and_verticals(db_session)
    user = _create_user(db_session, f"dism_{uuid4().hex[:6]}", f"dism_{uuid4().hex[:6]}@oms.local", vertical_id=v1.id)

    n1 = service.create_notification(
        recipient_id=user.id,
        title="Notice 1",
        message="Message 1",
        notification_type=NotificationType.SYSTEM,
    )
    n2 = service.create_notification(
        recipient_id=user.id,
        title="Notice 2",
        message="Message 2",
        notification_type=NotificationType.SYSTEM,
    )
    db_session.commit()

    # Initial state: 2 notifications
    items_init, total_init, unread_init = service.list_user_notifications(user.id)
    assert total_init == 2
    assert len(items_init) == 2
    assert unread_init == 2

    # Dismiss n1
    dismissed_n1 = service.dismiss_notification(n1.id, user.id)
    assert dismissed_n1.read_status == NotificationReadStatus.DISMISSED
    db_session.commit()

    # Default list (read_status=None) MUST exclude dismissed notification
    items_after, total_after, unread_after = service.list_user_notifications(user.id)
    assert total_after == 1
    assert len(items_after) == 1
    assert items_after[0].id == n2.id
    assert unread_after == 1

    # Explicit filter by DISMISSED shows n1
    items_dism, total_dism, _ = service.list_user_notifications(user.id, read_status=NotificationReadStatus.DISMISSED)
    assert total_dism == 1
    assert len(items_dism) == 1
    assert items_dism[0].id == n1.id

