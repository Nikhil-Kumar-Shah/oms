"""fix schema drift forms requirements form_versions

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-04 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Forms table missing columns
    form_cols = [c["name"] for c in inspector.get_columns("forms")]
    if "instructions" not in form_cols:
        op.add_column("forms", sa.Column("instructions", sa.Text(), nullable=True))
    if "category" not in form_cols:
        op.add_column("forms", sa.Column("category", sa.String(length=100), nullable=True, server_default="Operational"))

    # 2. Form Versions table missing columns
    form_ver_cols = [c["name"] for c in inspector.get_columns("form_versions")]
    if "sections" not in form_ver_cols:
        op.add_column(
            "form_versions",
            sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"))
        )
    if "review_config" not in form_ver_cols:
        op.add_column(
            "form_versions",
            sa.Column("review_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )

    # 3. Requirements table missing columns
    req_cols = [c["name"] for c in inspector.get_columns("requirements")]
    if "event_id" not in req_cols:
        op.add_column(
            "requirements",
            sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
        )
    if "responsible_poc_id" not in req_cols:
        op.add_column(
            "requirements",
            sa.Column("responsible_poc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        )
    if "forward_history" not in req_cols:
        op.add_column(
            "requirements",
            sa.Column("forward_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb"))
        )
    if "reference_link" not in req_cols:
        op.add_column("requirements", sa.Column("reference_link", sa.String(length=1024), nullable=True))

    # Add indexes on new foreign keys if not existing
    req_indexes = [idx["name"] for idx in inspector.get_indexes("requirements")]
    if "ix_requirements_event_id" not in req_indexes:
        op.create_index(op.f("ix_requirements_event_id"), "requirements", ["event_id"], unique=False)
    if "ix_requirements_responsible_poc_id" not in req_indexes:
        op.create_index(op.f("ix_requirements_responsible_poc_id"), "requirements", ["responsible_poc_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    req_indexes = [idx["name"] for idx in inspector.get_indexes("requirements")]
    if "ix_requirements_responsible_poc_id" in req_indexes:
        op.drop_index(op.f("ix_requirements_responsible_poc_id"), table_name="requirements")
    if "ix_requirements_event_id" in req_indexes:
        op.drop_index(op.f("ix_requirements_event_id"), table_name="requirements")

    req_cols = [c["name"] for c in inspector.get_columns("requirements")]
    if "reference_link" in req_cols:
        op.drop_column("requirements", "reference_link")
    if "forward_history" in req_cols:
        op.drop_column("requirements", "forward_history")
    if "responsible_poc_id" in req_cols:
        op.drop_column("requirements", "responsible_poc_id")
    if "event_id" in req_cols:
        op.drop_column("requirements", "event_id")

    form_ver_cols = [c["name"] for c in inspector.get_columns("form_versions")]
    if "review_config" in form_ver_cols:
        op.drop_column("form_versions", "review_config")
    if "sections" in form_ver_cols:
        op.drop_column("form_versions", "sections")

    form_cols = [c["name"] for c in inspector.get_columns("forms")]
    if "category" in form_cols:
        op.drop_column("forms", "category")
    if "instructions" in form_cols:
        op.drop_column("forms", "instructions")
