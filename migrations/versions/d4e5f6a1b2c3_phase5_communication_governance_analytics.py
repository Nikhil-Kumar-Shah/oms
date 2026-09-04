"""Phase 5: Communication + Governance + Analytics Schema Extensions

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-09-01 15:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add EVENT and EVENT_TEAM values to announcement_scope_enum
    op.execute("ALTER TYPE announcement_scope_enum ADD VALUE IF NOT EXISTS 'EVENT'")
    op.execute("ALTER TYPE announcement_scope_enum ADD VALUE IF NOT EXISTS 'EVENT_TEAM'")

    # 2. Add event_id to announcements table
    op.add_column(
        "announcements",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_announcements_event_id", "announcements", ["event_id"])

    # 3. Add event_id to communication_logs table
    op.add_column(
        "communication_logs",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_comm_logs_event_id", "communication_logs", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_comm_logs_event_id", table_name="communication_logs")
    op.drop_column("communication_logs", "event_id")

    op.drop_index("ix_announcements_event_id", table_name="announcements")
    op.drop_column("announcements", "event_id")
