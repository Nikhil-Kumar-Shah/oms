"""phase1_organization_event_team_poc

Revision ID: a1b2c3d4e5f6
Revises: f82c1de94a21
Create Date: 2026-09-01 14:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f82c1de94a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create event_team_profiles table
    op.create_table(
        "event_team_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_name", sa.String(255), nullable=False),
        sa.Column("head_name", sa.String(255), nullable=True),
        sa.Column("head_email", sa.String(255), nullable=True),
        sa.Column("head_phone", sa.String(50), nullable=True),
        sa.Column("members_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contact_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_event_team_profiles_user_id"), "event_team_profiles", ["user_id"], unique=True)
    op.create_index(op.f("ix_event_team_profiles_event_id"), "event_team_profiles", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_team_profiles_team_name"), "event_team_profiles", ["team_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_team_profiles_team_name"), table_name="event_team_profiles")
    op.drop_index(op.f("ix_event_team_profiles_event_id"), table_name="event_team_profiles")
    op.drop_index(op.f("ix_event_team_profiles_user_id"), table_name="event_team_profiles")
    op.drop_table("event_team_profiles")
