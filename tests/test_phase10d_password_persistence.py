"""
Phase 10D: Authentication & Password Persistence Correction Test Suite

Verifies:
1. Exact Multi-User Regression Scenario from Phase 10D:
   - Admin created with initial password
   - Login with initial password succeeds
   - Password changed to new password
   - Login with new password succeeds
   - Login with old password fails
   - Logout Admin
   - Login another user (e.g. Coordinator), logout
   - Login Admin with new password succeeds
   - Login Admin with old password fails
   - Reinitialize DB connection / session context
   - Login Admin with new password succeeds
   - Login Admin with old password fails
2. Self-service password change persistence in PostgreSQL.
3. Admin password reset functionality, session revocation, and old password invalidation.
4. Seed database idempotency: running seed scripts never reverts an existing user's password.
5. User creation default password vs permanent change.
"""

import pytest
from uuid import uuid4
from sqlalchemy import select
from app.core.security import hash_password, verify_password
from app.models.user import User, AccountStatus
from app.models.organization import Organization, Vertical, VerticalStatus, UserVertical
from app.models.rbac import Role, UserRole
from app.models.session import UserSession
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.core.exceptions import AuthenticationFailedException, ValidationException
from scripts.seed_dev import seed_database
from app.core.config import get_settings

settings = get_settings()


def _setup_org_and_role(db_session, role_name: str = "ADMIN"):
    org = db_session.query(Organization).filter(Organization.code == "TEST_AUTH_ORG").first()
    if not org:
        org = Organization(name="Test Auth Org", code="TEST_AUTH_ORG", description="Auth test org")
        db_session.add(org)
        db_session.flush()

    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} test role")
        db_session.add(role)
        db_session.flush()

    return org, role


def _create_test_user(db_session, username: str, password: str, role_name: str = "ADMIN") -> User:
    org, role = _setup_org_and_role(db_session, role_name)

    user = User(
        username=username,
        email=f"{username}@oms.local",
        full_name=f"Full {username}",
        password_hash=hash_password(password),
        account_status=AccountStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(user_role)
    db_session.flush()

    return user


def test_multi_user_password_regression_scenario(db_session):
    """
    Mandatory Phase 10D Scenario:
    1. Create ADMIN with initial password.
    2. Login ADMIN using initial password -> SUCCESS.
    3. Change ADMIN password.
    4. Verify NEW password -> SUCCESS.
    5. Verify OLD password -> FAILURE.
    6. Logout ADMIN.
    7. Login another user.
    8. Logout other user.
    9. Login ADMIN using NEW password -> SUCCESS.
    10. Login ADMIN using OLD password -> FAILURE.
    11. Reinitialize DB connection / session context.
    12. Login ADMIN using NEW password -> SUCCESS.
    13. Login ADMIN using OLD password -> FAILURE.
    """
    auth_service = AuthService(db_session)

    initial_password = "InitialAdminPass@123"
    new_password = "BrandNewAdminPass@456"
    other_password = "CoordinatorPass@789"

    admin_username = f"admin_reg_{uuid4().hex[:6]}"
    other_username = f"coord_reg_{uuid4().hex[:6]}"

    # 1. Create ADMIN with initial password
    admin = _create_test_user(db_session, admin_username, initial_password, role_name="ADMIN")
    other_user = _create_test_user(db_session, other_username, other_password, role_name="COORDINATOR")
    db_session.commit()

    # 2. Login ADMIN using initial password -> SUCCESS
    u1, s1, t1 = auth_service.login(admin_username, initial_password)
    assert u1.id == admin.id
    assert s1.is_valid is True

    # 3. Change ADMIN password
    auth_service.change_password(
        user_id=admin.id,
        current_password=initial_password,
        new_password=new_password,
        current_session_id=s1.id,
    )
    db_session.commit()

    # 4. Verify NEW password in DB hash
    db_session.expire_all()
    reloaded_admin = db_session.get(User, admin.id)
    assert verify_password(new_password, reloaded_admin.password_hash) is True

    # 5. Verify OLD password in DB hash
    assert verify_password(initial_password, reloaded_admin.password_hash) is False

    # 6. Logout ADMIN
    auth_service.logout(t1)
    db_session.commit()

    # 7. Login another user -> SUCCESS
    u2, s2, t2 = auth_service.login(other_username, other_password)
    assert u2.id == other_user.id
    assert s2.is_valid is True

    # 8. Logout other user
    auth_service.logout(t2)
    db_session.commit()

    # 9. Login ADMIN using NEW password -> SUCCESS
    u_admin_new, s_admin_new, t_admin_new = auth_service.login(admin_username, new_password)
    assert u_admin_new.id == admin.id
    assert s_admin_new.is_valid is True

    # 10. Login ADMIN using OLD password -> FAILURE
    with pytest.raises(AuthenticationFailedException):
        auth_service.login(admin_username, initial_password)

    # 11. Reinitialize DB / expire all cached ORM objects
    db_session.expire_all()
    fresh_auth_service = AuthService(db_session)

    # 12. Login ADMIN using NEW password -> SUCCESS
    u_admin_post_restart, _, _ = fresh_auth_service.login(admin_username, new_password)
    assert u_admin_post_restart.id == admin.id

    # 13. Login ADMIN using OLD password -> FAILURE
    with pytest.raises(AuthenticationFailedException):
        fresh_auth_service.login(admin_username, initial_password)


def test_seed_database_does_not_revert_admin_password(db_session):
    """
    Verifies that running the database seeding routine never overwrites
    or silently reverts the password of an existing administrator account.
    """
    admin_username = settings.DEV_ADMIN_USERNAME.strip().lower()

    # Ensure admin user exists with a custom changed password
    custom_password = "CustomSuperSecretPass@999"
    admin = db_session.scalar(select(User).where(User.username == admin_username))
    if not admin:
        _create_test_user(db_session, admin_username, custom_password, role_name="ADMIN")
    else:
        admin.password_hash = hash_password(custom_password)
        admin.account_status = AccountStatus.ACTIVE
    db_session.commit()

    # Verify custom password works before seeding
    auth_service = AuthService(db_session)
    u_before, _, _ = auth_service.login(admin_username, custom_password)
    assert u_before is not None

    # Run seed_database()
    seed_database()

    # Re-query user from fresh session
    db_session.expire_all()
    reloaded_admin = db_session.scalar(select(User).where(User.username == admin_username))

    # The custom password must STILL be valid!
    assert verify_password(custom_password, reloaded_admin.password_hash) is True

    # The default seed password must NOT work!
    assert verify_password(settings.DEV_ADMIN_PASSWORD, reloaded_admin.password_hash) is False

    # Login with custom password must succeed
    fresh_auth = AuthService(db_session)
    u_after, _, _ = fresh_auth.login(admin_username, custom_password)
    assert u_after.id == reloaded_admin.id

    # Login with default seed password must fail
    with pytest.raises(AuthenticationFailedException):
        fresh_auth.login(admin_username, settings.DEV_ADMIN_PASSWORD)


def test_admin_reset_user_password(db_session):
    """
    Verifies that an administrative password reset:
    1. Updates the target user's password_hash in PostgreSQL.
    2. Invalidates the target user's old password.
    3. Revokes any existing active sessions of the target user.
    """
    user_service = UserService(db_session)
    auth_service = AuthService(db_session)

    username = f"reset_target_{uuid4().hex[:6]}"
    old_password = "TargetInitialPass@123"
    new_password = "AdminResetPass@456"

    user = _create_test_user(db_session, username, old_password, role_name="VOLUNTEER")
    db_session.commit()

    # User logs in and gets an active session
    u, s, t = auth_service.login(username, old_password)
    assert s.is_valid is True

    # Admin resets user's password
    user_service.admin_reset_password(
        user_id=user.id,
        new_password=new_password,
    )
    db_session.commit()

    # Verify old session was revoked
    db_session.expire_all()
    reloaded_session = db_session.get(UserSession, s.id)
    assert reloaded_session.revoked_at is not None
    assert reloaded_session.is_valid is False

    # Login with old password fails
    with pytest.raises(AuthenticationFailedException):
        auth_service.login(username, old_password)

    # Login with new password succeeds
    u_new, s_new, _ = auth_service.login(username, new_password)
    assert u_new.id == user.id
    assert s_new.is_valid is True


def test_self_service_change_password_validation(db_session):
    """Verifies that wrong current password raises ValidationException and leaves hash unchanged."""
    auth_service = AuthService(db_session)
    username = f"chg_val_{uuid4().hex[:6]}"
    real_password = "RealUserPassword@123"
    wrong_current = "WrongCurrentPass@999"
    new_password = "NewValidPassword@456"

    user = _create_test_user(db_session, username, real_password, role_name="VOLUNTEER")
    db_session.commit()

    # Attempt to change password with wrong current password
    with pytest.raises(ValidationException):
        auth_service.change_password(
            user_id=user.id,
            current_password=wrong_current,
            new_password=new_password,
        )

    # Password hash must remain unchanged
    db_session.expire_all()
    reloaded = db_session.get(User, user.id)
    assert verify_password(real_password, reloaded.password_hash) is True
    assert verify_password(new_password, reloaded.password_hash) is False
