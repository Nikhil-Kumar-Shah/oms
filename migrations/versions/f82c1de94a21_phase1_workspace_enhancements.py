"""phase1_workspace_enhancements

Revision ID: f82c1de94a21
Revises: e71a8bc43d12
Create Date: 2026-09-01 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = 'f82c1de94a21'
down_revision: Union[str, None] = 'e71a8bc43d12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. User Profiles Table
    op.create_table(
        'user_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('phone_number', sa.String(length=50), nullable=True),
        sa.Column('specialization', sa.String(length=255), nullable=True),
        sa.Column('operational_capability', sa.Text(), nullable=True),
        sa.Column('certifications', JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('availability', postgresql.ENUM('AVAILABLE', 'BUSY', 'ON_LEAVE', 'INACTIVE', name='user_availability_enum', create_type=True), nullable=False, server_default='AVAILABLE'),
        sa.Column('profile_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'], unique=True)
    op.create_index('ix_user_profiles_availability', 'user_profiles', ['availability'], unique=False)

    # 2. Meeting Action Items Table
    op.create_table(
        'meeting_action_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('meeting_id', UUID(as_uuid=True), sa.ForeignKey('meetings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('assignee_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority', postgresql.ENUM('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', name='task_priority_enum', create_type=False), nullable=False, server_default='MEDIUM'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_converted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('converted_task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True, unique=True),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('converted_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_meeting_action_items_meeting_id', 'meeting_action_items', ['meeting_id'], unique=False)
    op.create_index('ix_meeting_action_items_assignee_id', 'meeting_action_items', ['assignee_id'], unique=False)
    op.create_index('ix_meeting_action_items_is_converted', 'meeting_action_items', ['is_converted'], unique=False)
    op.create_index('ix_meeting_action_items_converted_task_id', 'meeting_action_items', ['converted_task_id'], unique=True)

    # 3. Master Calendar Recurrence & Entity Linking
    rec_enum = postgresql.ENUM('NONE', 'DAILY', 'WEEKLY', 'MONTHLY', name='recurrence_frequency_enum', create_type=True)
    rec_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('calendar_entries', sa.Column('recurrence', postgresql.ENUM('NONE', 'DAILY', 'WEEKLY', 'MONTHLY', name='recurrence_frequency_enum', create_type=False), nullable=False, server_default='NONE'))
    op.add_column('calendar_entries', sa.Column('recurrence_end_date', sa.Date(), nullable=True))
    op.add_column('calendar_entries', sa.Column('task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True))
    op.add_column('calendar_entries', sa.Column('event_id', UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='SET NULL'), nullable=True))
    op.add_column('calendar_entries', sa.Column('meeting_id', UUID(as_uuid=True), sa.ForeignKey('meetings.id', ondelete='SET NULL'), nullable=True))
    op.add_column('calendar_entries', sa.Column('requirement_id', UUID(as_uuid=True), sa.ForeignKey('requirements.id', ondelete='SET NULL'), nullable=True))

    op.create_index('ix_calendar_entries_recurrence', 'calendar_entries', ['recurrence'], unique=False)
    op.create_index('ix_calendar_entries_task_id', 'calendar_entries', ['task_id'], unique=False)
    op.create_index('ix_calendar_entries_event_id', 'calendar_entries', ['event_id'], unique=False)
    op.create_index('ix_calendar_entries_meeting_id', 'calendar_entries', ['meeting_id'], unique=False)
    op.create_index('ix_calendar_entries_requirement_id', 'calendar_entries', ['requirement_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_calendar_entries_requirement_id', table_name='calendar_entries')
    op.drop_index('ix_calendar_entries_meeting_id', table_name='calendar_entries')
    op.drop_index('ix_calendar_entries_event_id', table_name='calendar_entries')
    op.drop_index('ix_calendar_entries_task_id', table_name='calendar_entries')
    op.drop_index('ix_calendar_entries_recurrence', table_name='calendar_entries')

    op.drop_column('calendar_entries', 'requirement_id')
    op.drop_column('calendar_entries', 'meeting_id')
    op.drop_column('calendar_entries', 'event_id')
    op.drop_column('calendar_entries', 'task_id')
    op.drop_column('calendar_entries', 'recurrence_end_date')
    op.drop_column('calendar_entries', 'recurrence')

    postgresql.ENUM(name='recurrence_frequency_enum').drop(op.get_bind(), checkfirst=True)

    op.drop_table('meeting_action_items')
    op.drop_table('user_profiles')

    postgresql.ENUM(name='user_availability_enum').drop(op.get_bind(), checkfirst=True)
