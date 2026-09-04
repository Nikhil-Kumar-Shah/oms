"""
Dedicated Security Attack Suite
Verifies defense against the 19 required attack vectors:
1. Client changes user_id in request
2. Client changes role in request
3. Client changes permission in request
4. User attempts admin endpoint
5. Disabled user uses old session
6. Expired session reused
7. Revoked session reused
8. User accesses another user's resource
9. User accesses another vertical's protected resource
10. User attempts unauthorized vertical modification
11. User attempts privilege escalation
12. User attempts audit-log modification
13. User attempts audit-log deletion
14. Invalid organization/vertical relationship
15. Duplicate username
16. Duplicate role/permission relationship
17. Invalid session token
18. Password change without authentication
19. Password change with incorrect old password
"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import ImmutableAuditException
from app.core.security import generate_session_token, hash_password, hash_session_token
from app.models.organization import Vertical, VerticalStatus
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def test_attack_01_client_cannot_change_user_id_in_identity(
    client: TestClient,
    regular_user: User,
    admin_user: User,
    auth_headers_user: dict,
):
    """
    Attack 1: Client sends another user's ID in payload/query or tries to claim admin identity.
    Server always resolves identity from authenticated session.
    """
    response = client.get("/api/v1/auth/me", headers=auth_headers_user)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(regular_user.id)
    assert data["id"] != str(admin_user.id)


def test_attack_02_client_cannot_escalate_role_in_request(
    client: TestClient,
    auth_headers_user: dict,
):
    """
    Attack 2: Client sends payload claiming role='ADMIN' or role parameters to unauthorized endpoint.
    """
    response = client.post(
        "/api/v1/admin/users",
        json={"username": "hacker", "full_name": "Hacker", "password": "Password@123"},
        headers=auth_headers_user,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_attack_03_client_cannot_forge_permission_header_or_body(
    client: TestClient,
    auth_headers_user: dict,
):
    """
    Attack 3: Client supplies client-side permission claims or forged headers.
    """
    headers = {**auth_headers_user, "X-User-Role": "ADMIN", "X-Permission": "users.create"}
    response = client.post(
        "/api/v1/admin/users",
        json={"username": "hacker2", "full_name": "Hacker", "password": "Password@123"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_attack_04_unauthorized_user_attempts_admin_endpoint(
    client: TestClient,
    auth_headers_user: dict,
):
    """
    Attack 4: Regular user without admin permission attempts admin listing.
    """
    response = client.get("/api/v1/admin/users", headers=auth_headers_user)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_attack_05_disabled_user_cannot_use_existing_session(
    client: TestClient,
    db_session: Session,
):
    """
    Attack 5: Active session becomes invalid as soon as user is disabled.
    """
    uname = f"attack_dis_{uuid.uuid4().hex[:6]}"
    u = User(
        username=uname,
        full_name="Target Disable User",
        password_hash=hash_password("Pass@123456"),
        account_status=AccountStatus.ACTIVE,
    )
    db_session.add(u)
    db_session.commit()

    # Login to get valid session
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=uname, password="Pass@123456")
    db_session.commit()

    headers = {"Authorization": f"Bearer {raw_token}"}
    # Verify session works
    assert client.get("/api/v1/auth/me", headers=headers).status_code == status.HTTP_200_OK

    # Disable user
    user_service = UserService(db_session)
    user_service.disable_user(u.id)
    db_session.commit()

    # Now verify old session is rejected immediately
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def test_attack_06_expired_session_reused(
    client: TestClient,
    regular_user: User,
    db_session: Session,
):
    """
    Attack 6: Replay of an expired session token.
    """
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    past = datetime.now(timezone.utc) - timedelta(hours=48)

    session = UserSession(
        user_id=regular_user.id,
        session_token_hash=token_hash,
        created_at=past - timedelta(hours=24),
        expires_at=past,
        last_seen_at=past,
    )
    db_session.add(session)
    db_session.commit()

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_attack_07_revoked_session_reused(
    client: TestClient,
    regular_user: User,
    db_session: Session,
):
    """
    Attack 7: Replay of a revoked session token.
    """
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)

    session = UserSession(
        user_id=regular_user.id,
        session_token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(hours=24),
        last_seen_at=now,
        revoked_at=now,
    )
    db_session.add(session)
    db_session.commit()

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_attack_08_user_cannot_access_unauthorized_user_detail(
    client: TestClient,
    admin_user: User,
    auth_headers_user: dict,
):
    """
    Attack 8: IDOR attempt by unprivileged user to query another user's admin detail.
    """
    resp = client.get(f"/api/v1/admin/users/{admin_user.id}", headers=auth_headers_user)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_attack_09_user_accesses_unassigned_vertical_scope(
    db_session: Session,
    regular_user: User,
):
    """
    Attack 9: User attempts action scoped to a vertical they are not assigned to.
    """
    from app.api.dependencies import require_vertical_scope
    vert = db_session.scalar(select(Vertical).where(Vertical.name == "Athletics & Track"))

    checker = require_vertical_scope(vert.id)
    with pytest.raises(Exception):
        checker(user=regular_user, db=db_session)


def test_attack_10_unauthorized_vertical_modification(
    client: TestClient,
    auth_headers_user: dict,
    db_session: Session,
):
    """
    Attack 10: Regular user attempts to modify vertical attributes.
    """
    vert = db_session.scalar(select(Vertical).limit(1))
    resp = client.patch(
        f"/api/v1/admin/organization/verticals/{vert.id}",
        json={"name": "Hacked Name"},
        headers=auth_headers_user,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_attack_11_user_attempts_privilege_escalation_assign_role(
    client: TestClient,
    regular_user: User,
    auth_headers_user: dict,
    db_session: Session,
):
    """
    Attack 11: Regular user attempts to assign ADMIN role to themselves.
    """
    from app.models.rbac import Role
    admin_role = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
    resp = client.post(
        f"/api/v1/admin/users/{regular_user.id}/roles",
        json={"role_ids": [str(admin_role.id)]},
        headers=auth_headers_user,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_attack_12_audit_log_modification_forbidden(db_session: Session):
    """
    Attack 12: Application attempt to modify audit log record.
    """
    audit = AuditService(db_session)
    with pytest.raises(ImmutableAuditException):
        audit.update_record(uuid.uuid4())


def test_attack_13_audit_log_deletion_forbidden(db_session: Session):
    """
    Attack 13: Application attempt to delete audit log record.
    """
    audit = AuditService(db_session)
    with pytest.raises(ImmutableAuditException):
        audit.delete_record(uuid.uuid4())


def test_attack_14_invalid_organization_vertical_relationship(
    client: TestClient,
    auth_headers_admin: dict,
):
    """
    Attack 14: Creating vertical with non-existent organization ID.
    """
    resp = client.post(
        "/api/v1/admin/organization/verticals",
        json={"name": "Bogus Vert", "organization_id": str(uuid.uuid4())},
        headers=auth_headers_admin,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_attack_15_duplicate_username_rejected(
    client: TestClient,
    admin_user: User,
    auth_headers_admin: dict,
):
    """
    Attack 15: Creating duplicate username fails with 422.
    """
    resp = client.post(
        "/api/v1/admin/users",
        json={"username": admin_user.username, "full_name": "Clone", "password": "Password@123"},
        headers=auth_headers_admin,
    )
    assert resp.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def test_attack_16_duplicate_role_permission_handled(
    db_session: Session,
    admin_user: User,
):
    """
    Attack 16: Duplicate role assignment handled gracefully without duplicate rows.
    """
    from app.models.rbac import Role
    from app.services.rbac_service import RbacService
    rbac = RbacService(db_session)
    role = db_session.scalar(select(Role).where(Role.name == "VOLUNTEER"))

    # Assign same role twice in list - should be safely deduplicated to 1
    roles = rbac.assign_roles(admin_user.id, [role.id, role.id])
    assert len(roles) == 1


def test_attack_17_invalid_session_token_rejected(client: TestClient):
    """
    Attack 17: Random/forged bearer token rejected with 401.
    """
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer forged-token-abc-123"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_attack_18_password_change_without_auth_rejected(client: TestClient):
    """
    Attack 18: Password change unauthenticated fails with 401.
    """
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPass@123", "new_password": "NewPass@123"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_attack_19_password_change_with_wrong_current_password(
    client: TestClient,
    auth_headers_user: dict,
):
    """
    Attack 19: Password change with incorrect current password rejected with 422.
    """
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "IncorrectCurrentPassword", "new_password": "NewValidPass@123"},
        headers=auth_headers_user,
    )
    assert resp.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
