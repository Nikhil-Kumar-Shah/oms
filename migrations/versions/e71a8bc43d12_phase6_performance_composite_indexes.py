"""phase6_performance_composite_indexes

Revision ID: e71a8bc43d12
Revises: 6bc680ff3919
Create Date: 2026-09-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71a8bc43d12'
down_revision: Union[str, None] = '6bc680ff3919'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tasks: composite indexing on assignment & vertical filtering
    op.create_index(
        'idx_tasks_assigned_status',
        'tasks',
        ['assigned_to_id', 'status'],
        unique=False,
    )
    op.create_index(
        'idx_tasks_vertical_status',
        'tasks',
        ['vertical_id', 'status'],
        unique=False,
    )

    # 2. Notifications: composite indexing on recipient attention feeds
    op.create_index(
        'idx_notifications_recipient_status_date',
        'notifications',
        ['recipient_id', 'read_status', 'created_at'],
        unique=False,
    )

    # 3. Directives: composite indexing on vertical compliance queries
    op.create_index(
        'idx_directives_vertical_status',
        'directives',
        ['vertical_id', 'status'],
        unique=False,
    )

    # 4. Events: composite indexing on vertical scheduling
    op.create_index(
        'idx_events_vertical_date',
        'events',
        ['vertical_id', 'planned_date'],
        unique=False,
    )

    # 5. Requirements: composite indexing on vertical incoming queue
    op.create_index(
        'idx_requirements_target_status',
        'requirements',
        ['target_vertical_id', 'status'],
        unique=False,
    )

    # 6. Issues: composite indexing on vertical sensitivity filtering
    op.create_index(
        'idx_issues_vertical_sensitivity_status',
        'issues',
        ['vertical_id', 'sensitivity', 'status'],
        unique=False,
    )

    # 7. Audit Logs: composite indexing on action and chronological ordering
    op.create_index(
        'idx_audit_logs_action_timestamp',
        'audit_logs',
        ['action', 'timestamp'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_audit_logs_action_timestamp', table_name='audit_logs')
    op.drop_index('idx_issues_vertical_sensitivity_status', table_name='issues')
    op.drop_index('idx_requirements_target_status', table_name='requirements')
    op.drop_index('idx_events_vertical_date', table_name='events')
    op.drop_index('idx_directives_vertical_status', table_name='directives')
    op.drop_index('idx_notifications_recipient_status_date', table_name='notifications')
    op.drop_index('idx_tasks_vertical_status', table_name='tasks')
    op.drop_index('idx_tasks_assigned_status', table_name='tasks')
