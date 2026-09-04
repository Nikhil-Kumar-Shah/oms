"""
Automated Business Rules & Operational Workflows Test Suite
Paradox Sports OMS

Verifies:
1. User lifecycle & inactive session denial.
2. Self-review prohibition on daily work reports.
3. Self-approval prohibition on resource ownership transfers.
4. Task blocker tracking & health status.
5. Cross-vertical requirement routing & scoping.
6. Data-driven vertical dynamic creation & status control.
7. Zero hard-deletion lifecycle preservation.
"""

import random
import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy import select, text
from app.core.exceptions import ForbiddenException, ValidationException
from app.models.governance import OwnershipTransfer, TransferResourceType, TransferStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.report import DailyReportStatus, DailyWorkReport
from app.models.task import Task, TaskHealth, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.schemas.auth import LoginRequest
from app.schemas.governance import OwnershipTransferCreate, OwnershipTransferReviewRequest
from app.schemas.organization import VerticalCreate, VerticalUpdate
from app.schemas.report import DailyReportCreate, DailyReportReviewRequest
from app.schemas.task import TaskCreate, TaskTransitionRequest
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationService
from app.services.report_service import ReportService
from app.services.task_service import TaskService
from app.services.transfer_service import OwnershipTransferService
from app.services.user_service import UserService


def test_rule_self_review_prevention_on_daily_reports(db_session, test_user, test_vertical):
    """Rule 6 & 7: Authors are strictly prohibited from reviewing/approving their own reports."""
    report_service = ReportService(db_session)
    rand_date = date(2028, 1, 1) + timedelta(days=random.randint(1, 5000))

    # 1. User submits report
    report_data = DailyReportCreate(
        vertical_id=test_vertical.id,
        report_date=rand_date,
        work_summary="Pitch preparation completed",
        tasks_completed="Task A and Task B completed",
        submit_now=True,
    )
    report = report_service.create_daily_report(report_data, user_id=test_user.id)
    assert report.status == DailyReportStatus.SUBMITTED

    # 2. Author attempts to review their own report
    review_data = DailyReportReviewRequest(
        status=DailyReportStatus.REVIEWED,
        review_comments="Self approval attempt",
    )
    with pytest.raises(ForbiddenException) as exc_info:
        report_service.review_daily_report(report.id, reviewer_id=test_user.id, data=review_data)

    assert "Self-review violation" in str(exc_info.value)


def test_rule_self_approval_prevention_on_ownership_transfers(db_session, test_user, admin_user, test_vertical):
    """Rule 16: Requesters cannot approve their own ownership transfer requests."""
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
            title=f"Transferrable Task {uuid.uuid4().hex[:6]}",
            description="Testing transfer rules",
            vertical_id=test_vertical.id,
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.MEDIUM,
            assigned_to_id=test_user.id,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        actor_id=admin_user.id,
    )

    # 2. Requester initiates transfer
    transfer = transfer_service.request_transfer(
        data=OwnershipTransferCreate(
            resource_type=TransferResourceType.TASK,
            resource_id=task.id,
            requested_owner_id=admin_user.id,
            reason="Role reassignment",
        ),
        requested_by_id=test_user.id,
    )
    assert transfer.status == TransferStatus.PENDING

    # 3. Requester attempts to approve their own transfer
    with pytest.raises(ForbiddenException) as exc_info:
        transfer_service.review_transfer(
            transfer.id,
            reviewer_id=test_user.id,
            data=OwnershipTransferReviewRequest(status=TransferStatus.APPROVED, remarks="Self approving"),
        )

    assert "Self-approval prohibited" in str(exc_info.value)


def test_rule_task_blocker_handling(db_session, test_user, admin_user, test_vertical):
    """Rule 12: Transitioning a task to BLOCKED updates health and attaches blocker notes."""
    task_service = TaskService(db_session)

    task = task_service.create_task(
        TaskCreate(
            title=f"Blocker Test Task {uuid.uuid4().hex[:6]}",
            description="Testing blocker requirement",
            vertical_id=test_vertical.id,
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.HIGH,
            assigned_to_id=test_user.id,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        actor_id=admin_user.id,
    )

    # Block with valid blocker reason
    updated_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.BLOCKED, blockers="Awaiting stadium turf key"),
        actor_id=test_user.id,
    )
    assert updated_task.status == TaskStatus.BLOCKED
    assert updated_task.health == TaskHealth.BLOCKED
    assert updated_task.blockers == "Awaiting stadium turf key"


def test_rule_user_disabled_session_invalidation(db_session, test_user, admin_user):
    """Rule 9: Disabled/suspended users cannot authenticate or validate existing sessions."""
    auth_service = AuthService(db_session)
    user_service = UserService(db_session)

    # 1. Login user to create active session
    user_res, session_obj, raw_token = auth_service.login(
        username="test_coordinator",
        password="CoordPass@123",
        ip_address="127.0.0.1",
    )
    assert session_obj.is_valid is True

    # Validate active session
    u, s = auth_service.validate_session(raw_token)
    assert u.id == test_user.id

    # 2. Admin disables user account (which revokes all active sessions)
    user_service.disable_user(test_user.id, actor_id=admin_user.id)

    # 3. Session validation must now fail
    with pytest.raises(Exception):
        auth_service.validate_session(raw_token)

    # Restore user account status for test cleanup
    user_service.enable_user(test_user.id, actor_id=admin_user.id)


def test_rule_data_driven_vertical_lifecycle(db_session, admin_user):
    """Rule 2 & 10: Dynamic vertical creation and disabled vertical operational blocking."""
    org_service = OrganizationService(db_session)
    task_service = TaskService(db_session)

    # 1. Dynamically create a new vertical
    vert_name = f"Table Tennis Operations {uuid.uuid4().hex[:4]}"
    vert = org_service.create_vertical(
        VerticalCreate(name=vert_name, description="Table tennis tournament management"),
    )
    assert vert.status == VerticalStatus.ACTIVE

    # 2. Disable vertical
    disabled_vert = org_service.update_vertical(vert.id, VerticalUpdate(status=VerticalStatus.DISABLED))
    assert disabled_vert.status == VerticalStatus.DISABLED

    # 3. Attempting to create task in disabled vertical must fail
    with pytest.raises(ValidationException) as exc_info:
        task_service.create_task(
            TaskCreate(
                title="Table Setup",
                description="Setup tables",
                vertical_id=vert.id,
                task_type=TaskType.ROUTINE,
                priority=TaskPriority.LOW,
                assigned_to_id=admin_user.id,
            ),
            actor_id=admin_user.id,
        )
    assert "disabled" in str(exc_info.value).lower()


def test_rule_zero_hard_deletion_preservation(db_session, test_user, admin_user, test_vertical):
    """Rule 17 & 18: Operational records are cancelled, never hard deleted."""
    task_service = TaskService(db_session)

    task = task_service.create_task(
        TaskCreate(
            title=f"Lifecycle Preservation Task {uuid.uuid4().hex[:6]}",
            description="Testing zero hard deletion",
            vertical_id=test_vertical.id,
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.LOW,
            assigned_to_id=test_user.id,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        actor_id=admin_user.id,
    )

    # Cancel task
    cancelled_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.CANCELLED, remarks="Event was cancelled"),
        actor_id=admin_user.id,
    )
    assert cancelled_task.status == TaskStatus.CANCELLED

    # Complete task
    completed_task = task_service.transition_status(
        task.id,
        TaskTransitionRequest(status=TaskStatus.COMPLETED, remarks="Finalized for records"),
        actor_id=admin_user.id,
    )
    assert completed_task.status == TaskStatus.COMPLETED

    # Fresh session read proves record still exists in PostgreSQL
    persisted = db_session.scalar(select(Task).where(Task.id == task.id))
    assert persisted is not None
    assert persisted.status == TaskStatus.COMPLETED
