"""
RBAC, Permissions & Overrides Test Suite
"""

import uuid
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.rbac import Permission, Role
from app.models.user import AccountStatus, User
from app.services.rbac_service import RbacService


def test_list_canonical_roles(client: TestClient, auth_headers_admin: dict):
    """Verifies listing roles returns all canonical OMS roles."""
    response = client.get("/api/v1/admin/roles", headers=auth_headers_admin)
    assert response.status_code == status.HTTP_200_OK
    roles = response.json()
    role_names = [r["name"] for r in roles]
    assert "ADMIN" in role_names
    assert "SPORTS_CORE" in role_names
    assert "COORDINATOR" in role_names
    assert "VOLUNTEER" in role_names


def test_effective_permissions_calculation(db_session: Session):
    """Verifies (Role Perms + Grants) - Revokes calculation."""
    rbac = RbacService(db_session)

    # 1. Create a user with COORDINATOR role
    u = User(
        username=f"rbac_calc_{uuid.uuid4().hex[:6]}",
        full_name="RBAC Calc User",
        password_hash=hash_password("Pass@123456"),
        account_status=AccountStatus.ACTIVE,
    )
    db_session.add(u)
    db_session.flush()

    coord_role = rbac.get_role_by_name("COORDINATOR")
    rbac.assign_roles(u.id, [coord_role.id])

    # Initial effective permissions
    initial_perms = rbac.get_effective_permissions(u.id)
    assert "users.read" in initial_perms
    assert "users.create" not in initial_perms

    # 2. Grant explicit override for 'users.create'
    create_perm = db_session.scalar(
        select(Permission).where(Permission.code == "users.create")
    )
    read_perm = db_session.scalar(
        select(Permission).where(Permission.code == "users.read")
    )

    overrides = [
        {"permission_id": create_perm.id, "is_granted": True},   # +grant
        {"permission_id": read_perm.id, "is_granted": False},    # -revoke
    ]
    rbac.set_permission_overrides(u.id, overrides)

    # Re-calculate effective permissions
    effective_perms = rbac.get_effective_permissions(u.id)

    # Explicit grant should be present
    assert "users.create" in effective_perms
    # Explicit revoke should be removed even though present in role
    assert "users.read" not in effective_perms


def test_admin_has_all_permissions(db_session: Session, admin_user: User):
    """Verifies ADMIN role possesses all permissions in the system."""
    rbac = RbacService(db_session)
    effective_perms = rbac.get_effective_permissions(admin_user.id)
    all_perms = rbac.list_permissions()

    assert len(effective_perms) == len(all_perms)
    for p in all_perms:
        assert p.code in effective_perms
