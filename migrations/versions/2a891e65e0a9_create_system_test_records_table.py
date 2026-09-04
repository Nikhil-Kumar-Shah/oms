"""create_system_test_records_table

Revision ID: 2a891e65e0a9
Revises: 
Create Date: 2026-09-01 02:53:26.563352

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2a891e65e0a9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_test_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_system_test_records')),
    )
    op.create_index(op.f('ix_system_test_records_id'), 'system_test_records', ['id'], unique=False)
    op.create_index(op.f('ix_system_test_records_name'), 'system_test_records', ['name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_test_records_name'), table_name='system_test_records')
    op.drop_index(op.f('ix_system_test_records_id'), table_name='system_test_records')
    op.drop_table('system_test_records')
