"""
Tests for Announcements & Broadcasts System
"""

import pytest
from app.models.communication import AnnouncementPriority, AnnouncementScope, AnnouncementStatus
from app.models.organization import Vertical
from app.models.user import User
from app.schemas.communication import AnnouncementCreate, AnnouncementUpdate
from app.services.announcement_service import AnnouncementService
from app.services.notification_service import NotificationService


def test_create_and_publish_announcement(db_session, admin_user):
    """Verifies creating draft and publishing announcement."""
    service = AnnouncementService(db_session)
    data = AnnouncementCreate(
        title="Annual Sports Tournament 2026",
        content="Registrations are now open for all sports disciplines.",
        category="EVENT",
        priority=AnnouncementPriority.HIGH,
        scope=AnnouncementScope.ALL,
        publish_now=False,
    )
    ann = service.create_announcement(data, author_id=admin_user.id)
    db_session.commit()

    assert ann.id is not None
    assert ann.status == AnnouncementStatus.DRAFT
    assert ann.published_at is None

    # Publish
    pub = service.publish_announcement(ann.id, actor_id=admin_user.id)
    db_session.commit()

    assert pub.status == AnnouncementStatus.PUBLISHED
    assert pub.published_at is not None


def test_announcement_scoping_and_notifications(db_session, admin_user, test_user, test_vertical):
    """Verifies that vertical-scoped announcement creates attention notifications for vertical members."""
    service = AnnouncementService(db_session)
    notif_service = NotificationService(db_session)

    data = AnnouncementCreate(
        title="Logistics Division Briefing",
        content="All logistics volunteers must assemble at 09:00 AM.",
        category="LOGISTICS",
        priority=AnnouncementPriority.URGENT,
        scope=AnnouncementScope.VERTICAL,
        vertical_id=test_vertical.id,
        publish_now=True,
    )
    ann = service.create_announcement(data, author_id=admin_user.id)
    db_session.commit()

    assert ann.status == AnnouncementStatus.PUBLISHED

    # Check notification dispatched to test_user (assigned to test_vertical)
    notifs, total, unread = notif_service.list_user_notifications(user_id=test_user.id)
    assert total >= 1
    assert any(n.related_resource_id == ann.id for n in notifs)


def test_archive_announcement(db_session, admin_user):
    """Verifies archiving of announcements."""
    service = AnnouncementService(db_session)
    data = AnnouncementCreate(
        title="Old Broadcast",
        content="Expiring broadcast details.",
        publish_now=True,
    )
    ann = service.create_announcement(data, author_id=admin_user.id)
    archived = service.archive_announcement(ann.id, actor_id=admin_user.id)
    db_session.commit()

    assert archived.status == AnnouncementStatus.ARCHIVED
    assert archived.archived_at is not None
