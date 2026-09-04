"""
Tests for Notification Attention Engine & Isolation
"""

import pytest
from app.core.exceptions import ForbiddenException
from app.models.communication import NotificationReadStatus, NotificationType
from app.services.notification_service import NotificationService


def test_notification_creation_and_lifecycle(db_session, test_user):
    """Verifies notification dispatch, read-status update, and mark-all-as-read."""
    service = NotificationService(db_session)

    n1 = service.create_notification(
        recipient_id=test_user.id,
        title="Task Assigned",
        message="You have been assigned to setup venue ground.",
        notification_type=NotificationType.TASK,
    )
    n2 = service.create_notification(
        recipient_id=test_user.id,
        title="Meeting Scheduled",
        message="Core sync scheduled for tomorrow.",
        notification_type=NotificationType.MEETING,
    )
    db_session.commit()

    assert n1.id is not None
    assert n2.id is not None

    notifs, total, unread = service.list_user_notifications(user_id=test_user.id)
    assert total >= 2
    assert unread >= 2

    # Mark single as read
    service.mark_as_read(n1.id, user_id=test_user.id)
    db_session.commit()

    _, _, unread_after = service.list_user_notifications(user_id=test_user.id)
    assert unread_after == unread - 1

    # Mark all read
    cnt = service.mark_all_as_read(user_id=test_user.id)
    db_session.commit()
    assert cnt >= 1

    _, _, unread_final = service.list_user_notifications(user_id=test_user.id)
    assert unread_final == 0


def test_notification_idor_isolation(db_session, admin_user, test_user):
    """Verifies that a user cannot access or dismiss another user's notifications."""
    service = NotificationService(db_session)

    admin_notif = service.create_notification(
        recipient_id=admin_user.id,
        title="Admin Alert",
        message="System configuration changed.",
    )
    db_session.commit()

    # Attempting to read/dismiss as test_user must raise ForbiddenException
    with pytest.raises(ForbiddenException):
        service.mark_as_read(admin_notif.id, user_id=test_user.id)

    with pytest.raises(ForbiddenException):
        service.dismiss_notification(admin_notif.id, user_id=test_user.id)
