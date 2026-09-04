"""Phase 10I: Issue Assignees Junction Table for Multi-Target Assignment

Revision ID: b81e3a7f2c4d
Revises: a94d8f1e2c3b
Create Date: 2026-09-03 20:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b81e3a7f2c4d'
down_revision = 'a94d8f1e2c3b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create issue_assignees junction table
    op.create_table(
        'issue_assignees',
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_issue_assignees_user_id', 'issue_assignees', ['user_id'])
    op.create_index('ix_issue_assignees_issue_id', 'issue_assignees', ['issue_id'])

    # 2. Backfill existing single assignees from issues.assigned_to_id into issue_assignees
    op.execute("""
        INSERT INTO issue_assignees (issue_id, user_id, created_at)
        SELECT id, assigned_to_id, created_at
        FROM issues
        WHERE assigned_to_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_index('ix_issue_assignees_issue_id', table_name='issue_assignees')
    op.drop_index('ix_issue_assignees_user_id', table_name='issue_assignees')
    op.drop_table('issue_assignees')
