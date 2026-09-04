"""phase10h_calendar_lifecycle_and_individual_completion

Revision ID: a94d8f1e2c3b
Revises: e82b9c4f1d0a
Create Date: 2026-09-03 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a94d8f1e2c3b"
down_revision: Union[str, None] = "e82b9c4f1d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to calendar_entry_users for individual participant completion
    op.add_column(
        "calendar_entry_users",
        sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "calendar_entry_users",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Add columns to calendar_entries for rescheduling audit
    op.add_column(
        "calendar_entries",
        sa.Column("original_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "calendar_entries",
        sa.Column("rescheduled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Add enum values to calendar_status_enum if needed
    # Note: In PostgreSQL, ALTER TYPE ... ADD VALUE must be executed outside a multi-statement transaction block
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE calendar_status_enum ADD VALUE IF NOT EXISTS 'UPCOMING'"))
    conn.execute(sa.text("ALTER TYPE calendar_status_enum ADD VALUE IF NOT EXISTS 'RESCHEDULED'"))
    conn.execute(sa.text("BEGIN"))


def downgrade() -> None:
    op.drop_column("calendar_entries", "rescheduled_at")
    op.drop_column("calendar_entries", "original_date")
    op.drop_column("calendar_entry_users", "completed_at")
    op.drop_column("calendar_entry_users", "is_completed")
