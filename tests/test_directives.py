"""
Tests for Operational Directives & Compliance Roster
"""

import pytest
from app.models.communication import (
    AcknowledgementStatus,
    DirectivePriority,
    DirectiveScope,
    DirectiveStatus,
)
from app.schemas.communication import DirectiveAcknowledgeRequest, DirectiveCreate
from app.services.directive_service import DirectiveService
from app.services.notification_service import NotificationService


def test_create_and_issue_directive_with_acknowledgements(db_session, admin_user, test_user, test_vertical):
    """Verifies issuing directive creates pending acknowledgements and notifications for members."""
    service = DirectiveService(db_session)
    notif_service = NotificationService(db_session)

    data = DirectiveCreate(
        title="Mandatory Security Protocol Compliance",
        instruction="Every event coordinator must submit visitor rosters 24 hours in advance.",
        priority=DirectivePriority.HIGH,
        scope=DirectiveScope.VERTICAL,
        vertical_id=test_vertical.id,
        requires_acknowledgement=True,
        issue_now=True,
    )
    directive = service.create_directive(data, issued_by_id=admin_user.id)
    db_session.commit()

    assert directive.id is not None
    assert directive.status == DirectiveStatus.ISSUED

    # Verify acknowledgement record was initialized
    fetched = service.get_directive_by_id(directive.id)
    assert len(fetched.acknowledgements) >= 1
    user_ack = next((a for a in fetched.acknowledgements if a.user_id == test_user.id), None)
    assert user_ack is not None
    assert user_ack.status == AcknowledgementStatus.PENDING

    # Verify notification created
    notifs, total, unread = notif_service.list_user_notifications(user_id=test_user.id)
    assert any(n.related_resource_id == directive.id for n in notifs)

    # Perform user acknowledgement
    ack_req = DirectiveAcknowledgeRequest(notes="Understood and confirmed compliance.")
    ack_res = service.acknowledge_directive(directive.id, user_id=test_user.id, data=ack_req)
    db_session.commit()

    assert ack_res.status == AcknowledgementStatus.ACKNOWLEDGED
    assert ack_res.acknowledged_at is not None
    assert ack_res.notes == "Understood and confirmed compliance."
