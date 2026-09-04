"""Seed canonical roles and permissions

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.services.rbac_service import ensure_canonical_roles_and_permissions

# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    role_map = ensure_canonical_roles_and_permissions(session)

    # Automatically heal any user created without roles during initial setup (e.g. test.core)
    try:
        from app.models.user import User
        from app.models.rbac import UserRole
        users_without_roles = session.query(User).outerjoin(UserRole).filter(UserRole.id == None).all()
        sports_core_role = role_map.get("SPORTS_CORE")
        if sports_core_role:
            for u in users_without_roles:
                if "core" in u.username.lower():
                    session.add(UserRole(user_id=u.id, role_id=sports_core_role.id))
    except Exception:
        pass

    session.commit()


def downgrade() -> None:
    pass
