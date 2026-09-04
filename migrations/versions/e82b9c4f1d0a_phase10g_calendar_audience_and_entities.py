"""Phase 10G: Calendar Audience & Entity Projections

Revision ID: e82b9c4f1d0a
Revises: d4e5f6a1b2c3
Create Date: 2026-09-03 19:30:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e82b9c4f1d0a"
down_revision: Union[str, None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add entity_type and entity_id to calendar_entries table
    op.add_column(
        "calendar_entries",
        sa.Column("entity_type", sa.String(50), nullable=True, server_default="CALENDAR_ENTRY"),
    )
    op.add_column(
        "calendar_entries",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_calendar_entries_entity_type", "calendar_entries", ["entity_type"])
    op.create_index("ix_calendar_entries_entity_id", "calendar_entries", ["entity_id"])

    # 2. Create calendar_entry_users association table
    op.create_table(
        "calendar_entry_users",
        sa.Column(
            "calendar_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendar_entries.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_calendar_entry_users_user_id",
        "calendar_entry_users",
        ["user_id"],
    )

    # 3. Seed calendar.read_master permission if missing and associate with ADMIN, SPORTS_CORE, DEPUTY_CORE
    op.execute(
        """
        DO $$
        DECLARE
            perm_id UUID;
            role_rec RECORD;
        BEGIN
            -- Check or insert permission
            SELECT id INTO perm_id FROM permissions WHERE code = 'calendar.read_master';
            IF perm_id IS NULL THEN
                perm_id := gen_random_uuid();
                INSERT INTO permissions (id, code, description, category, created_at)
                VALUES (perm_id, 'calendar.read_master', 'View master organizational calendar', 'WORK', NOW());
            END IF;

            -- Associate with executive roles
            FOR role_rec IN SELECT id FROM roles WHERE name IN ('ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE') LOOP
                INSERT INTO role_permissions (role_id, permission_id, created_at)
                SELECT role_rec.id, perm_id, NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM role_permissions WHERE role_id = role_rec.id AND permission_id = perm_id
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # Remove calendar_entry_users
    op.drop_index("ix_calendar_entry_users_user_id", table_name="calendar_entry_users")
    op.drop_table("calendar_entry_users")

    # Remove entity_type and entity_id
    op.drop_index("ix_calendar_entries_entity_id", table_name="calendar_entries")
    op.drop_index("ix_calendar_entries_entity_type", table_name="calendar_entries")
    op.drop_column("calendar_entries", "entity_id")
    op.drop_column("calendar_entries", "entity_type")

    # Remove calendar.read_master permission
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'calendar.read_master')")
    op.execute("DELETE FROM permissions WHERE code = 'calendar.read_master'")
