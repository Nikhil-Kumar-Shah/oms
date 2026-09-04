"""
Tests for Ownership Transfer Governance
"""

from datetime import datetime, timezone
import pytest
from app.core.exceptions import ForbiddenException
from app.models.governance import TransferResourceType, TransferStatus
from app.models.task import Task, TaskPriority, TaskType
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest
from app.services.task_service import TaskService
from app.services.transfer_service import OwnershipTransferService


def test_task_ownership_transfer_workflow(db_session, admin_user, test_user, test_vertical):
    """Verifies complete request, review, approval, and atomic task reassignment."""
    task_service = TaskService(db_session)
    transfer_service = OwnershipTransferService(db_session)

    # 1. Create a task assigned to admin_user
    task = Task(
        title="Medal Distribution Management",
        description="Oversee distribution of tournament medals",
        vertical_id=test_vertical.id,
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        assigned_to_id=admin_user.id,
        assigned_by_id=admin_user.id,
    )
    db_session.add(task)
    db_session.flush()

    assert task.assigned_to_id == admin_user.id

    # 2. Request transfer to test_user
    req_data = OwnershipTransferCreate(
        resource_type=TransferResourceType.TASK,
        resource_id=task.id,
        requested_owner_id=test_user.id,
        reason="Admin delegating on-ground execution to coordinator.",
    )
    transfer = transfer_service.request_transfer(req_data, requested_by_id=admin_user.id)
    db_session.commit()

    assert transfer.id is not None
    assert transfer.status == TransferStatus.PENDING

    # 3. Test self-approval prevention (requester cannot approve)
    with pytest.raises(ForbiddenException):
        transfer_service.review_transfer(
            transfer.id,
            reviewer_id=admin_user.id,
            data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED),
        )

    # 4. Review and approve as another authorized supervisor/test_user
    reviewed = transfer_service.review_transfer(
        transfer.id,
        reviewer_id=test_user.id,
        data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Accepted handover."),
    )
    db_session.commit()

    assert reviewed.status == TransferStatus.COMPLETED

    # 5. Verify task assignee was updated in PostgreSQL
    db_session.refresh(task)
    assert task.assigned_to_id == test_user.id
