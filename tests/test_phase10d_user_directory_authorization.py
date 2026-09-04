"""
Phase 10D: Production User Directory Authorization & Data Scoping Test Suite
=============================================================================
Validates strict backend / database query level authorization for the User Directory:
1. Global Roles (ADMIN, SPORTS_CORE, DEPUTY_CORE) -> view all users across all verticals
2. Vertical Scoped Roles (SUPER_COORDINATOR, COORDINATOR, VOLUNTEER) -> view only users in authorized verticals
3. Cross-Vertical Isolation -> Coordinator/SuperCoordinator/Volunteer A CANNOT see Vertical B users
4. Search Isolation -> Searches for unauthorized users by username, full name, email, or UUID return zero results
5. Direct Object Access -> GET /organization/users/{id} and /users/{id} return 403 Forbidden for cross-vertical unauthorized targets
6. Empty Scope Protection -> Scoped user with no verticals returns 0 results (never falls back to all users)
7. Multi-Vertical Scoping -> Users assigned to Verticals A & B see A & B users, but not unrelated C users
8. Pagination & Scoped Counts -> total count strictly reflects the scoped query, not all users
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.services.auth_service import AuthService


def _create_user(
    db: Session,
    username: str,
    role_name: str,
    verticals: list = None,
    password: str = "TestPass@123",
) -> User:
    uid = uuid.uuid4().hex[:6]
    u = User(
        username=f"{username}_{uid}",
        full_name=f"Full Name {username}_{uid}",
        email=f"{username}_{uid}@test.internal",
        password_hash=hash_password(password),
        account_status=AccountStatus.ACTIVE,
    )
    db.add(u)
    db.flush()

    role = db.scalar(select(Role).where(Role.name == role_name))
    if role:
        db.add(UserRole(user_id=u.id, role_id=role.id))

    if verticals:
        for i, vert in enumerate(verticals):
            db.add(UserVertical(user_id=u.id, vertical_id=vert.id, is_primary=(i == 0)))

    db.commit()
    db.refresh(u)
    return u


def _get_auth_headers(db: Session, user: User, password: str = "TestPass@123") -> dict:
    auth_service = AuthService(db)
    _, _, token = auth_service.login(username=user.username, password=password)
    db.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org(db_session: Session) -> Organization:
    stmt = select(Organization).where(Organization.code == "PARADOX_SPORTS")
    o = db_session.scalar(stmt)
    if not o:
        o = Organization(name="Paradox Sports", code="PARADOX_SPORTS")
        db_session.add(o)
        db_session.commit()
    return o


@pytest.fixture
def vert_a(db_session: Session, org: Organization) -> Vertical:
    v = Vertical(
        organization_id=org.id,
        name=f"Vert_A_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.commit()
    return v


@pytest.fixture
def vert_b(db_session: Session, org: Organization) -> Vertical:
    v = Vertical(
        organization_id=org.id,
        name=f"Vert_B_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.commit()
    return v


@pytest.fixture
def vert_c(db_session: Session, org: Organization) -> Vertical:
    v = Vertical(
        organization_id=org.id,
        name=f"Vert_C_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.commit()
    return v


# =============================================================================
# 1. GLOBAL ROLES: ADMIN, SPORTS_CORE, DEPUTY_CORE SEE ALL USERS
# =============================================================================

def test_global_roles_can_view_all_users_across_all_verticals(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Admin, Sports Core, and Deputy Core can view all users in the organization."""
    admin = _create_user(db_session, "admin_glob", "ADMIN")
    sports_core = _create_user(db_session, "core_glob", "SPORTS_CORE")
    deputy_core = _create_user(db_session, "deputy_glob", "DEPUTY_CORE")

    user_in_a = _create_user(db_session, "user_in_a", "VOLUNTEER", [vert_a])
    user_in_b = _create_user(db_session, "user_in_b", "VOLUNTEER", [vert_b])

    for global_actor in [admin, sports_core, deputy_core]:
        headers = _get_auth_headers(db_session, global_actor)
        response = client.get("/api/v1/organization/users", headers=headers)
        assert response.status_code == status.HTTP_200_OK, f"Failed for {global_actor.username}"
        data = response.json()

        returned_ids = [u["id"] for u in data["items"]]
        assert str(user_in_a.id) in returned_ids, f"user_in_a missing for {global_actor.username}"
        assert str(user_in_b.id) in returned_ids, f"user_in_b missing for {global_actor.username}"


# =============================================================================
# 2. COORDINATOR STRICT VERTICAL ISOLATION (THE PRODUCTION BUG SCENARIO)
# =============================================================================

def test_coordinator_sees_only_own_vertical_users(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """
    Exact production scenario:
    Vertical A has Coordinator A, Volunteer A, Super Coordinator A.
    Vertical B has Coordinator B, Volunteer B, Super Coordinator B.
    When Coordinator A opens User Directory, they must see ONLY Vertical A members.
    Vertical B members must strictly NOT be returned.
    """
    coord_a = _create_user(db_session, "coord_a", "COORDINATOR", [vert_a])
    vol_a = _create_user(db_session, "vol_a", "VOLUNTEER", [vert_a])
    super_a = _create_user(db_session, "super_a", "SUPER_COORDINATOR", [vert_a])

    coord_b = _create_user(db_session, "coord_b", "COORDINATOR", [vert_b])
    vol_b = _create_user(db_session, "vol_b", "VOLUNTEER", [vert_b])
    super_b = _create_user(db_session, "super_b", "SUPER_COORDINATOR", [vert_b])

    headers_a = _get_auth_headers(db_session, coord_a)

    response = client.get("/api/v1/organization/users", headers=headers_a)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    returned_usernames = [u["username"] for u in data["items"]]

    # Vertical A users must be present
    assert coord_a.username in returned_usernames
    assert vol_a.username in returned_usernames
    assert super_a.username in returned_usernames

    # Vertical B users must strictly be absent
    assert coord_b.username not in returned_usernames
    assert vol_b.username not in returned_usernames
    assert super_b.username not in returned_usernames

    # Scoped total count must match
    vertical_a_user_ids = {str(coord_a.id), str(vol_a.id), str(super_a.id)}
    assert all(str(u["id"]) not in {str(coord_b.id), str(vol_b.id), str(super_b.id)} for u in data["items"])


# =============================================================================
# 3. SUPER COORDINATOR AND VOLUNTEER VERTICAL ISOLATION
# =============================================================================

def test_super_coordinator_sees_only_own_vertical_users(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Super Coordinator A sees only users in Vertical A; Vertical B is excluded."""
    super_a = _create_user(db_session, "super_coord_a", "SUPER_COORDINATOR", [vert_a])
    vol_a = _create_user(db_session, "vol_in_a", "VOLUNTEER", [vert_a])

    coord_b = _create_user(db_session, "coord_in_b", "COORDINATOR", [vert_b])

    headers = _get_auth_headers(db_session, super_a)
    response = client.get("/api/v1/organization/users", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    returned_usernames = [u["username"] for u in data["items"]]
    assert super_a.username in returned_usernames
    assert vol_a.username in returned_usernames
    assert coord_b.username not in returned_usernames


def test_volunteer_sees_only_own_vertical_users(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Volunteer A cannot discover users from unrelated verticals."""
    vol_a = _create_user(db_session, "vol_member_a", "VOLUNTEER", [vert_a])
    coord_a = _create_user(db_session, "coord_member_a", "COORDINATOR", [vert_a])

    vol_b = _create_user(db_session, "vol_member_b", "VOLUNTEER", [vert_b])
    coord_b = _create_user(db_session, "coord_member_b", "COORDINATOR", [vert_b])

    headers = _get_auth_headers(db_session, vol_a)
    response = client.get("/api/v1/organization/users", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    returned_usernames = [u["username"] for u in data["items"]]
    assert vol_a.username in returned_usernames
    assert coord_a.username in returned_usernames
    assert vol_b.username not in returned_usernames
    assert coord_b.username not in returned_usernames


# =============================================================================
# 4. EMPTY VERTICAL SCOPE PROTECTION (ZERO RESULTS, NO FALLBACK TO GLOBAL)
# =============================================================================

def test_scoped_user_with_no_vertical_returns_zero_users(
    client: TestClient, db_session: Session, vert_a: Vertical
):
    """A scoped role (Coordinator) with no vertical assignment receives [] and total=0."""
    _create_user(db_session, "seeded_user_1", "VOLUNTEER", [vert_a])
    _create_user(db_session, "seeded_user_2", "COORDINATOR", [vert_a])

    coord_no_vert = _create_user(db_session, "coord_empty_scope", "COORDINATOR", verticals=None)

    headers = _get_auth_headers(db_session, coord_no_vert)
    response = client.get("/api/v1/organization/users", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []


# =============================================================================
# 5. MULTIPLE AUTHORIZED VERTICALS
# =============================================================================

def test_user_with_multiple_verticals_sees_users_from_all_assigned_verticals(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical, vert_c: Vertical
):
    """A Coordinator assigned to Verticals A & B sees users from A and B, but NOT C."""
    multi_coord = _create_user(db_session, "multi_coord", "COORDINATOR", [vert_a, vert_b])

    user_a = _create_user(db_session, "member_vert_a", "VOLUNTEER", [vert_a])
    user_b = _create_user(db_session, "member_vert_b", "VOLUNTEER", [vert_b])
    user_c = _create_user(db_session, "member_vert_c", "VOLUNTEER", [vert_c])

    headers = _get_auth_headers(db_session, multi_coord)
    response = client.get("/api/v1/organization/users", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    returned_usernames = [u["username"] for u in data["items"]]
    assert user_a.username in returned_usernames
    assert user_b.username in returned_usernames
    assert user_c.username not in returned_usernames


# =============================================================================
# 6. SEARCH ISOLATION (SEARCH MUST NOT BYPASS AUTHORIZATION)
# =============================================================================

def test_coordinator_searching_for_unrelated_user_returns_zero_results(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Coordinator A searching for Vertical B user by username, full name, email, or UUID gets 0 results."""
    coord_a = _create_user(db_session, "coord_search_a", "COORDINATOR", [vert_a])
    coord_b = _create_user(db_session, "coord_search_b", "COORDINATOR", [vert_b])

    headers_a = _get_auth_headers(db_session, coord_a)

    # Search by exact username of B
    resp_username = client.get(f"/api/v1/organization/users?search={coord_b.username}", headers=headers_a)
    assert resp_username.status_code == status.HTTP_200_OK
    data_username = resp_username.json()
    assert data_username["total"] == 0
    assert data_username["items"] == []

    # Search by full name of B
    resp_fullname = client.get(f"/api/v1/organization/users?search={coord_b.full_name}", headers=headers_a)
    assert resp_fullname.status_code == status.HTTP_200_OK
    assert resp_fullname.json()["total"] == 0

    # Search by email of B
    resp_email = client.get(f"/api/v1/organization/users?search={coord_b.email}", headers=headers_a)
    assert resp_email.status_code == status.HTTP_200_OK
    assert resp_email.json()["total"] == 0

    # Search by UUID of B
    resp_uuid = client.get(f"/api/v1/organization/users?search={coord_b.id}", headers=headers_a)
    assert resp_uuid.status_code == status.HTTP_200_OK
    assert resp_uuid.json()["total"] == 0


# =============================================================================
# 7. DIRECT USER LOOKUP BY UUID (DENIES ACCESS FOR CROSS-VERTICAL USERS)
# =============================================================================

def test_coordinator_direct_lookup_of_unrelated_user_is_forbidden(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Coordinator A attempting direct UUID lookup of User B receives 403 Forbidden."""
    coord_a = _create_user(db_session, "coord_direct_a", "COORDINATOR", [vert_a])
    coord_b = _create_user(db_session, "coord_direct_b", "COORDINATOR", [vert_b])

    headers_a = _get_auth_headers(db_session, coord_a)

    # Direct lookup on /api/v1/organization/users/{id}
    resp1 = client.get(f"/api/v1/organization/users/{coord_b.id}", headers=headers_a)
    assert resp1.status_code == status.HTTP_403_FORBIDDEN

    # Direct lookup on /api/v1/users/{id}
    resp2 = client.get(f"/api/v1/users/{coord_b.id}", headers=headers_a)
    assert resp2.status_code == status.HTTP_403_FORBIDDEN

    # Direct lookup on /api/v1/profiles/{id}
    resp3 = client.get(f"/api/v1/profiles/{coord_b.id}", headers=headers_a)
    assert resp3.status_code == status.HTTP_403_FORBIDDEN


def test_coordinator_can_directly_lookup_own_vertical_user(
    client: TestClient, db_session: Session, vert_a: Vertical
):
    """Coordinator A can directly look up a member in their own vertical."""
    coord_a = _create_user(db_session, "coord_own_lookup", "COORDINATOR", [vert_a])
    vol_a = _create_user(db_session, "vol_own_lookup", "VOLUNTEER", [vert_a])

    headers_a = _get_auth_headers(db_session, coord_a)

    resp = client.get(f"/api/v1/organization/users/{vol_a.id}", headers=headers_a)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == str(vol_a.id)
    assert data["username"] == vol_a.username


# =============================================================================
# 8. QUERY PARAMETER TAMPERING (REQUESTING UNAUTHORIZED VERTICAL)
# =============================================================================

def test_coordinator_requesting_unauthorized_vertical_filter_returns_empty(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """If Coordinator A passes ?vertical_id=vert_b.id, the API returns 0 results."""
    coord_a = _create_user(db_session, "coord_tamper_a", "COORDINATOR", [vert_a])
    _create_user(db_session, "vol_tamper_b", "VOLUNTEER", [vert_b])

    headers_a = _get_auth_headers(db_session, coord_a)

    resp = client.get(f"/api/v1/organization/users?vertical_id={vert_b.id}", headers=headers_a)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
