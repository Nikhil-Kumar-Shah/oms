"""
Tests for Official Communication Tracker
"""

import pytest
from app.models.communication import CommunicationLogStatus, CommunicationType
from app.schemas.communication import CommunicationLogCreate, CommunicationLogUpdate
from app.services.communication_service import CommunicationLogService


def test_create_and_update_communication_log(db_session, admin_user, test_vertical):
    """Verifies creating and searching official communication logs."""
    service = CommunicationLogService(db_session)

    data = CommunicationLogCreate(
        subject="Ground Booking Permission Clearance",
        communication_type=CommunicationType.OFFICIAL_MESSAGE,
        sender_info="Campus Estate Office",
        recipient_info="Paradox Sports Operations Head",
        vertical_id=test_vertical.id,
        reference_link="https://internal.paradox/letters/estate-001.pdf",
        remarks="Clearance granted for 15-20 October.",
    )
    log = service.create_log(data, created_by_id=admin_user.id)
    db_session.commit()

    assert log.id is not None
    assert log.status == CommunicationLogStatus.RECORDED

    # Update remarks
    update_payload = CommunicationLogUpdate(remarks="Clearance confirmed with zero fees.")
    updated = service.update_log(log.id, update_payload, actor_id=admin_user.id)
    db_session.commit()

    assert updated.remarks == "Clearance confirmed with zero fees."

    # List
    items, total = service.list_logs(vertical_id=test_vertical.id)
    assert total >= 1
    assert any(i.id == log.id for i in items)
