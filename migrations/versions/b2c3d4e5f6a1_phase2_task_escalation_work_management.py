"""phase2_task_escalation_work_management

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 14:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add escalation columns to tasks table
    op.add_column("tasks", sa.Column("is_escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("tasks", sa.Column("escalated_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tasks", sa.Column("escalated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tasks", sa.Column("escalation_reason", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("escalation_status", sa.String(50), nullable=True))
    op.add_column("tasks", sa.Column("escalation_resolution", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("escalation_resolved_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(op.f("ix_tasks_is_escalated"), "tasks", ["is_escalated"], unique=False)
    op.create_index(op.f("ix_tasks_escalated_to_id"), "tasks", ["escalated_to_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_escalated_to_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_is_escalated"), table_name="tasks")
    op.drop_column("tasks", "escalation_resolved_at")
    op.drop_column("tasks", "escalation_resolution")
    op.drop_column("tasks", "escalation_status")
    op.drop_column("tasks", "escalated_at")
    op.drop_column("tasks", "escalation_reason")
    op.drop_column("tasks", "escalated_by_id")
    op.drop_column("tasks", "escalated_to_id")
    op.drop_column("tasks", "is_escalated")
