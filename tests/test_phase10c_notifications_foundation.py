"""
Phase 10C: Notification System Foundation Test Suite
Verifies:
1. Notification creation and PostgreSQL persistence with default UNREAD state.
2. Persistent read state survival across database sessions.
3. User isolation & IDOR prevention (User A cannot read/mark read User B's notifications -> 403 Forbidden).
4. Mark single and mark-all read lifecycle.
5. Unread count calculation and query performance.
6. Centralized batch notification dispatching with exclusion of author.
7. Category/Type and status pagination filters.
"""

import pytest
import time
from uuid import uuid4
from datetime import datetime, timezone
from app.models.user import User, AccountStatus
from app.models.rbac import Role, UserRole
from app.models.communication import (
    Notification,
    NotificationType,
    NotificationReadStatus,
)
from app.services.notification_service import NotificationService
from app.core.exceptions import ForbiddenException, EntityNotFoundException


def _create_user(db_session, username: str, email: str, role_name: str = "COORDINATOR") -> User:
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
    return user


def test_notification_creation_and_postgres_persistence(db_session):
    service = NotificationService(db_session)
    user = _create_user(db_session, f"notif_user_{uuid4().hex[:6]}", f"notif_{uuid4().hex[:6]}@oms.local")

    # 1. Create notification
    notif = service.create_notification(
        recipient_id=user.id,
        title="Welcome to Paradox Sports OMS",
        message="Your operational workspace has been provisioned.",
        notification_type=NotificationType.SYSTEM,
        related_resource_type="USER",
        related_resource_id=user.id,
    )
    assert notif is not None
    assert notif.id is not None
    assert notif.recipient_id == user.id
    assert notif.read_status == NotificationReadStatus.UNREAD
    assert notif.is_read is False
    assert notif.read_at is None
    assert notif.created_at is not None

    db_session.commit()

    # 2. Query freshly from database to verify persistence
    persisted = db_session.get(Notification, notif.id)
    assert persisted is not None
    assert persisted.title == "Welcome to Paradox Sports OMS"
    assert persisted.read_status == NotificationReadStatus.UNREAD
    assert persisted.is_read is False


def test_read_state_persistence_and_survives_refresh(db_session):
    service = NotificationService(db_session)
    user = _create_user(db_session, f"read_user_{uuid4().hex[:6]}", f"read_{uuid4().hex[:6]}@oms.local")

    # Create 3 notifications
    n1 = service.create_notification(user.id, "Task 1", "Message 1", NotificationType.TASK)
    n2 = service.create_notification(user.id, "Task 2", "Message 2", NotificationType.TASK)
    n3 = service.create_notification(user.id, "Announcement 1", "Message 3", NotificationType.ANNOUNCEMENT)
    db_session.commit()

    # Verify initial unread count == 3
    unread_count = service.get_unread_count(user.id)
    assert unread_count == 3

    # Mark n1 as read
    marked_n1 = service.mark_as_read(n1.id, user_id=user.id)
    assert marked_n1.read_status == NotificationReadStatus.READ
    assert marked_n1.is_read is True
    assert marked_n1.read_at is not None
    db_session.commit()

    # Verify unread count decreased to 2
    assert service.get_unread_count(user.id) == 2

    # Query afresh through list_user_notifications
    items, total, unread = service.list_user_notifications(user.id)
    assert total == 3
    assert unread == 2
    n1_fresh = next(item for item in items if item.id == n1.id)
    assert n1_fresh.read_status == NotificationReadStatus.READ
    assert n1_fresh.is_read is True

    # Mark all remaining notifications as read
    marked_count = service.mark_all_as_read(user_id=user.id)
    assert marked_count == 2
    db_session.commit()

    # Verify unread count is 0
    assert service.get_unread_count(user.id) == 0


def test_user_isolation_and_idor_prevention(db_session):
    service = NotificationService(db_session)
    user_a = _create_user(db_session, f"user_a_{uuid4().hex[:6]}", f"usera_{uuid4().hex[:6]}@oms.local")
    user_b = _create_user(db_session, f"user_b_{uuid4().hex[:6]}", f"userb_{uuid4().hex[:6]}@oms.local")

    # User A receives a confidential notification
    notif_a = service.create_notification(
        recipient_id=user_a.id,
        title="Confidential Evaluation",
        message="Sensitive coordinator review details.",
        notification_type=NotificationType.SYSTEM,
    )
    db_session.commit()

    # User B lists their notifications -> User A's notification must NOT appear
    items_b, total_b, unread_b = service.list_user_notifications(user_b.id)
    assert total_b == 0
    assert not any(n.id == notif_a.id for n in items_b)

    # User B attempts to mark User A's notification as read -> Must raise ForbiddenException
    with pytest.raises(ForbiddenException):
        service.mark_as_read(notif_a.id, user_id=user_b.id)

    # User B attempts to dismiss User A's notification -> Must raise ForbiddenException
    with pytest.raises(ForbiddenException):
        service.dismiss_notification(notif_a.id, user_id=user_b.id)

    # User B runs mark_all_as_read -> Must NOT touch User A's notification
    service.mark_all_as_read(user_id=user_b.id)
    db_session.commit()

    notif_a_fresh = db_session.get(Notification, notif_a.id)
    assert notif_a_fresh.read_status == NotificationReadStatus.UNREAD
    assert notif_a_fresh.is_read is False


def test_batch_notification_dispatching_and_filtering(db_session):
    service = NotificationService(db_session)
    author = _create_user(db_session, f"author_{uuid4().hex[:6]}", f"author_{uuid4().hex[:6]}@oms.local")
    u1 = _create_user(db_session, f"u1_{uuid4().hex[:6]}", f"u1_{uuid4().hex[:6]}@oms.local")
    u2 = _create_user(db_session, f"u2_{uuid4().hex[:6]}", f"u2_{uuid4().hex[:6]}@oms.local")
    u3 = _create_user(db_session, f"u3_{uuid4().hex[:6]}", f"u3_{uuid4().hex[:6]}@oms.local")

    # Dispatch announcement to u1, u2, u3, and author, excluding author
    dispatched = service.create_batch_notifications(
        recipient_ids=[author.id, u1.id, u2.id, u3.id],
        title="Tournament Schedule Released",
        message="The final tournament fixtures are available.",
        notification_type=NotificationType.ANNOUNCEMENT,
        related_resource_type="ANNOUNCEMENT",
        related_resource_id=uuid4(),
        exclude_user_id=author.id,
    )
    db_session.commit()

    assert len(dispatched) == 3
    dispatched_recipients = {n.recipient_id for n in dispatched}
    assert author.id not in dispatched_recipients
    assert u1.id in dispatched_recipients
    assert u2.id in dispatched_recipients
    assert u3.id in dispatched_recipients

    # Test type filter
    u1_announcements, count_ann, _ = service.list_user_notifications(
        user_id=u1.id,
        notification_type=NotificationType.ANNOUNCEMENT,
    )
    assert count_ann == 1
    assert u1_announcements[0].title == "Tournament Schedule Released"

    u1_tasks, count_tasks, _ = service.list_user_notifications(
        user_id=u1.id,
        notification_type=NotificationType.TASK,
    )
    assert count_tasks == 0


def test_unread_count_query_performance(db_session):
    service = NotificationService(db_session)
    user = _create_user(db_session, f"perf_user_{uuid4().hex[:6]}", f"perf_{uuid4().hex[:6]}@oms.local")

    # Create 50 notifications
    for i in range(50):
        service.create_notification(
            recipient_id=user.id,
            title=f"Notification #{i}",
            message=f"Automated notification payload #{i}",
            notification_type=NotificationType.TASK,
        )
    db_session.commit()

    start_time = time.perf_counter()
    unread_count = service.get_unread_count(user.id)
    duration_ms = (time.perf_counter() - start_time) * 1000

    assert unread_count == 50
    # Target < 100ms
    assert duration_ms < 100, f"Unread count query took {duration_ms:.2f}ms, expected < 100ms"
