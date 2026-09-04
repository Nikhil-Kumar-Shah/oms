"""Phase 10D: Event Lifecycle State and Nullable Planned Date

Revision ID: a2b3c4d5e6f7
Revises: c92f4b8e3d5a
Create Date: 2026-09-04 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'c92f4b8e3d5a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add 'NOT_STARTED' to PostgreSQL event_status_enum type safely
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        # Check if NOT_STARTED already exists in enum
        existing = bind.execute(sa.text(
            "SELECT enumlabel FROM pg_enum WHERE enumtypid = 'event_status_enum'::regtype AND enumlabel = 'NOT_STARTED';"
        )).scalar()
        if not existing:
            op.execute("ALTER TYPE event_status_enum ADD VALUE IF NOT EXISTS 'NOT_STARTED' AFTER 'PLANNING';")

    # 2. Make planned_date nullable on events table to support minimal event creation
    op.alter_column(
        'events',
        'planned_date',
        existing_type=sa.Date(),
        nullable=True,
    )


def downgrade() -> None:
    # Set default date for any null records before setting NOT NULL back
    op.execute("UPDATE events SET planned_date = CURRENT_DATE WHERE planned_date IS NULL;")
    op.alter_column(
        'events',
        'planned_date',
        existing_type=sa.Date(),
        nullable=False,
    )
    # Note: PostgreSQL enum values cannot be easily removed without recreating the type
