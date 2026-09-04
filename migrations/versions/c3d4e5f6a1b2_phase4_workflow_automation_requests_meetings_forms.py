"""phase4_workflow_automation_requests_meetings_forms

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-09-01 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add escalation columns to requirements table
    op.add_column("requirements", sa.Column("is_escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("requirements", sa.Column("escalated_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("requirements", sa.Column("escalated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("requirements", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requirements", sa.Column("escalation_reason", sa.Text(), nullable=True))
    op.add_column("requirements", sa.Column("escalation_status", sa.String(50), nullable=True))
    op.add_column("requirements", sa.Column("escalation_resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requirements", sa.Column("escalation_resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("requirements", sa.Column("escalation_resolution_notes", sa.Text(), nullable=True))

    op.create_index(op.f("ix_requirements_is_escalated"), "requirements", ["is_escalated"], unique=False)
    op.create_index(op.f("ix_requirements_escalated_to_id"), "requirements", ["escalated_to_id"], unique=False)

    # 2. Add request workflow columns to meetings table
    op.add_column("meetings", sa.Column("is_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("meetings", sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    op.create_index(op.f("ix_meetings_is_requested"), "meetings", ["is_requested"], unique=False)
    op.create_index(op.f("ix_meetings_requested_by_id"), "meetings", ["requested_by_id"], unique=False)

    # 3. Add event_id column to forms table
    op.add_column("forms", sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True))
    op.create_index(op.f("ix_forms_event_id"), "forms", ["event_id"], unique=False)

    # 4. Add Enum values for PostgreSQL native enums if needed
    op.execute("ALTER TYPE meeting_status_enum ADD VALUE IF NOT EXISTS 'REQUESTED'")
    op.execute("ALTER TYPE meeting_status_enum ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.execute("ALTER TYPE meeting_type_enum ADD VALUE IF NOT EXISTS 'EVENT_TEAM_SYNC'")
    op.execute("ALTER TYPE form_audience_enum ADD VALUE IF NOT EXISTS 'EVENT'")
    op.execute("ALTER TYPE form_audience_enum ADD VALUE IF NOT EXISTS 'EVENT_TEAM'")


def downgrade() -> None:
    op.drop_index(op.f("ix_forms_event_id"), table_name="forms")
    op.drop_column("forms", "event_id")

    op.drop_index(op.f("ix_meetings_requested_by_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_is_requested"), table_name="meetings")
    op.drop_column("meetings", "requested_by_id")
    op.drop_column("meetings", "is_requested")

    op.drop_index(op.f("ix_requirements_escalated_to_id"), table_name="requirements")
    op.drop_index(op.f("ix_requirements_is_escalated"), table_name="requirements")
    op.drop_column("requirements", "escalation_resolution_notes")
    op.drop_column("requirements", "escalation_resolved_by_id")
    op.drop_column("requirements", "escalation_resolved_at")
    op.drop_column("requirements", "escalation_status")
    op.drop_column("requirements", "escalation_reason")
    op.drop_column("requirements", "escalated_at")
    op.drop_column("requirements", "escalated_by_id")
    op.drop_column("requirements", "escalated_to_id")
    op.drop_column("requirements", "is_escalated")
