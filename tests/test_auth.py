"""
Authentication, Sessions & Credential Test Suite
"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.session import UserSession
from app.models.user import AccountStatus, User


def test_login_success(client: TestClient, admin_user: User):
    """Verifies valid credentials authenticate and return session + cookie."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "AdminPass@123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "session" in data
    assert "token" in data["session"]
    assert data["user"]["username"] == admin_user.username
    assert "ADMIN" in [r["name"] for r in data["user"]["roles"]]
    assert "oms_session" in response.cookies


def test_login_success_with_email(client: TestClient, admin_user: User):
    """Verifies user can authenticate using registered email address."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.email, "password": "AdminPass@123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "session" in data
    assert data["user"]["username"] == admin_user.username
    assert data["user"]["email"] == admin_user.email
    assert "oms_session" in response.cookies


def test_login_invalid_username_returns_generic_401(client: TestClient):
    """Verifies non-existent username returns generic 401 without user enumeration."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user_9999", "password": "SomePassword@123"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTHENTICATION_FAILED"


def test_login_invalid_password_returns_generic_401(client: TestClient, admin_user: User):
    """Verifies incorrect password returns generic 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "WrongPassword@123"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTHENTICATION_FAILED"


def test_login_disabled_account_rejected(client: TestClient, db_session: Session):
    """Verifies DISABLED account cannot authenticate."""
    u = User(
        username=f"disabled_user_{uuid.uuid4().hex[:6]}",
        full_name="Disabled User",
        password_hash=hash_password("Pass@123456"),
        account_status=AccountStatus.DISABLED,
    )
    db_session.add(u)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": u.username, "password": "Pass@123456"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["error"]["code"] == "ACCOUNT_INACTIVE"


def test_login_suspended_account_rejected(client: TestClient, db_session: Session):
    """Verifies SUSPENDED account cannot authenticate."""
    u = User(
        username=f"suspended_user_{uuid.uuid4().hex[:6]}",
        full_name="Suspended User",
        password_hash=hash_password("Pass@123456"),
        account_status=AccountStatus.SUSPENDED,
    )
    db_session.add(u)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": u.username, "password": "Pass@123456"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_logout_revokes_session(client: TestClient, regular_user: User):
    """Verifies logging out revokes session and rejects further authenticated requests."""
    # 1. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": regular_user.username, "password": "VolunteerPass@123"},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    token = login_resp.json()["session"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify /me works
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == status.HTTP_200_OK

    # 3. Logout
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == status.HTTP_200_OK

    # 4. Verify /me is now rejected (401)
    revoked_resp = client.get("/api/v1/auth/me", headers=headers)
    assert revoked_resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_expired_session_rejected(client: TestClient, db_session: Session, regular_user: User):
    """Verifies an expired session is rejected."""
    # Create expired session directly
    from app.core.security import generate_session_token, hash_session_token
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    session = UserSession(
        user_id=regular_user.id,
        session_token_hash=token_hash,
        created_at=past_time - timedelta(hours=24),
        expires_at=past_time,
        last_seen_at=past_time,
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_change_password_success_and_invalid_current(client: TestClient, db_session: Session):
    """Verifies password change requires correct current password and updates hash."""
    uname = f"pwd_user_{uuid.uuid4().hex[:6]}"
    u = User(
        username=uname,
        full_name="Password Test User",
        password_hash=hash_password("OldPassword@123"),
        account_status=AccountStatus.ACTIVE,
    )
    db_session.add(u)
    db_session.commit()

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": uname, "password": "OldPassword@123"},
    )
    token = login_resp.json()["session"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Attempt change with incorrect current password -> 422/400
    bad_resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongOldPassword", "new_password": "NewSecurePassword@123"},
        headers=headers,
    )
    assert bad_resp.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

    # 2. Change with valid current password -> 200
    good_resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword@123", "new_password": "NewSecurePassword@123"},
        headers=headers,
    )
    assert good_resp.status_code == status.HTTP_200_OK

    # 3. Verify can login with new password
    new_login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": uname, "password": "NewSecurePassword@123"},
    )
    assert new_login_resp.status_code == status.HTTP_200_OK
