"""Phase 10J: Daily Report Tasks, Review Hierarchy, and History

Revision ID: c92f4b8e3d5a
Revises: b81e3a7f2c4d
Create Date: 2026-09-03 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c92f4b8e3d5a'
down_revision = 'b81e3a7f2c4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add reviewed_by_id to daily_work_reports and weekly_reports
    op.add_column(
        'daily_work_reports',
        sa.Column('reviewed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_daily_work_reports_reviewed_by_id', 'daily_work_reports', ['reviewed_by_id'])

    op.add_column(
        'weekly_reports',
        sa.Column('reviewed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_weekly_reports_reviewed_by_id', 'weekly_reports', ['reviewed_by_id'])

    # 2. Create daily_report_tasks junction table
    op.create_table(
        'daily_report_tasks',
        sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_work_reports.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('progress_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_daily_report_tasks_task_id', 'daily_report_tasks', ['task_id'])
    op.create_index('ix_daily_report_tasks_report_id', 'daily_report_tasks', ['report_id'])

    # 3. Create daily_report_history table
    op.create_table(
        'daily_report_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_work_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_daily_report_history_report_id', 'daily_report_history', ['report_id'])
    op.create_index('ix_daily_report_history_actor_id', 'daily_report_history', ['actor_id'])


def downgrade() -> None:
    op.drop_table('daily_report_history')
    op.drop_table('daily_report_tasks')
    op.drop_index('ix_weekly_reports_reviewed_by_id', table_name='weekly_reports')
    op.drop_column('weekly_reports', 'reviewed_by_id')
    op.drop_index('ix_daily_work_reports_reviewed_by_id', table_name='daily_work_reports')
    op.drop_column('daily_work_reports', 'reviewed_by_id')
