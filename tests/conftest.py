"""
Pytest Fixtures and Test Environment Setup
"""

import os
from typing import Dict, Generator, Tuple
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.base import Base
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Permission, Role, RolePermission, UserPermissionOverride, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User
from app.services.auth_service import AuthService
from app.services.rbac_service import CANONICAL_ROLES, CORE_PERMISSIONS, RbacService

settings = get_settings()

test_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensures database tables are created and seeded before running tests."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        # Seed Organization
        stmt = select(Organization).where(Organization.code == "PARADOX_SPORTS")
        org = db.scalar(stmt)
        if not org:
            org = Organization(
                name="Paradox Sports Department",
                code="PARADOX_SPORTS",
                description="Test organization",
            )
            db.add(org)
            db.flush()

        # Seed Verticals
        for name in ["Football Operations", "Cricket Operations", "Athletics & Track"]:
            stmt = select(Vertical).where(Vertical.organization_id == org.id, Vertical.name == name)
            if not db.scalar(stmt):
                db.add(Vertical(organization_id=org.id, name=name, status=VerticalStatus.ACTIVE))

        # Seed Permissions
        perm_map = {}
        for code, desc, cat in CORE_PERMISSIONS:
            stmt = select(Permission).where(Permission.code == code)
            perm = db.scalar(stmt)
            if not perm:
                perm = Permission(code=code, description=desc, category=cat)
                db.add(perm)
                db.flush()
            perm_map[code] = perm

        # Seed Roles
        for rname, rdesc in CANONICAL_ROLES:
            stmt = select(Role).where(Role.name == rname)
            role = db.scalar(stmt)
            if not role:
                role = Role(name=rname, description=rdesc, is_system=True)
                db.add(role)
                db.flush()

            # Ensure all permissions are present on ADMIN
            if rname == "ADMIN":
                for p in perm_map.values():
                    existing = db.scalar(select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.permission_id == p.id))
                    if not existing:
                        db.add(RolePermission(role_id=role.id, permission_id=p.id))

        # Ensure Dev Admin User exists
        admin_username = settings.DEV_ADMIN_USERNAME.strip().lower()
        stmt = select(User).where(User.username == admin_username)
        admin = db.scalar(stmt)
        if not admin:
            admin = User(
                username=admin_username,
                full_name="System Administrator",
                email="admin@paradoxsports.internal",
                password_hash=hash_password(settings.DEV_ADMIN_PASSWORD),
                account_status=AccountStatus.ACTIVE,
            )
            db.add(admin)
            db.flush()
            admin_role = db.scalar(select(Role).where(Role.name == "ADMIN"))
            if admin_role:
                db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
        else:
            admin.password_hash = hash_password(settings.DEV_ADMIN_PASSWORD)
            admin.account_status = AccountStatus.ACTIVE

        db.commit()
    finally:
        db.close()


from app.core.middleware import RateLimitingMiddleware


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides an isolated database session per test."""
    RateLimitingMiddleware.reset()
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        RateLimitingMiddleware.reset()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provides a TestClient with overridden database session."""
    RateLimitingMiddleware.reset()
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    RateLimitingMiddleware.reset()


@pytest.fixture
def test_vertical(db_session: Session) -> Vertical:
    """Fixture providing a primary active vertical."""
    stmt = select(Vertical).where(Vertical.name == "Football Operations")
    vert = db_session.scalar(stmt)
    if not vert:
        org = db_session.scalar(select(Organization).limit(1))
        vert = Vertical(name="Football Operations", organization_id=org.id, status=VerticalStatus.ACTIVE)
        db_session.add(vert)
        db_session.commit()
    return vert


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Fixture providing an active administrator user."""
    stmt = select(User).where(User.username == "test_admin")
    user = db_session.scalar(stmt)
    if not user:
        user = User(
            username="test_admin",
            full_name="Test Administrator",
            email="test_admin@paradoxsports.internal",
            password_hash=hash_password("AdminPass@123"),
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(user)
        db_session.flush()

        admin_role = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
        if admin_role:
            db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db_session.commit()
    else:
        user.password_hash = hash_password("AdminPass@123")
        user.account_status = AccountStatus.ACTIVE
        admin_role = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
        if admin_role:
            has_role = db_session.scalar(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
            )
            if not has_role:
                db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db_session.commit()
    return user


@pytest.fixture
def regular_user(db_session: Session) -> User:
    """Fixture providing an active regular user (VOLUNTEER role, unassigned to Football Operations)."""
    stmt = select(User).where(User.username == "test_volunteer")
    user = db_session.scalar(stmt)
    if not user:
        user = User(
            username="test_volunteer",
            full_name="Test Volunteer",
            email="test_volunteer@paradoxsports.internal",
            password_hash=hash_password("VolunteerPass@123"),
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(user)
        db_session.flush()

        role = db_session.scalar(select(Role).where(Role.name == "VOLUNTEER"))
        if role:
            db_session.add(UserRole(user_id=user.id, role_id=role.id))
        db_session.commit()
    else:
        user.password_hash = hash_password("VolunteerPass@123")
        user.account_status = AccountStatus.ACTIVE
        # Ensure test_volunteer is not assigned to Football Operations
        from app.models.organization import Vertical
        foot_vert = db_session.scalar(select(Vertical).where(Vertical.name == "Football Operations"))
        if foot_vert:
            existing_uv = db_session.scalar(
                select(UserVertical).where(
                    UserVertical.user_id == user.id,
                    UserVertical.vertical_id == foot_vert.id,
                )
            )
            if existing_uv:
                db_session.delete(existing_uv)
        db_session.commit()
    return user


@pytest.fixture
def coordinator_user(db_session: Session, test_vertical: Vertical) -> User:
    """Fixture providing an active coordinator user assigned to Football Operations."""
    stmt = select(User).where(User.username == "test_coordinator")
    user = db_session.scalar(stmt)
    if not user:
        user = User(
            username="test_coordinator",
            full_name="Test Coordinator",
            email="test_coordinator@paradoxsports.internal",
            password_hash=hash_password("CoordPass@123"),
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(user)
        db_session.flush()

        role = db_session.scalar(select(Role).where(Role.name == "COORDINATOR"))
        if role:
            db_session.add(UserRole(user_id=user.id, role_id=role.id))

        db_session.add(UserVertical(user_id=user.id, vertical_id=test_vertical.id, is_primary=True))
        db_session.commit()
    else:
        user.password_hash = hash_password("CoordPass@123")
        user.account_status = AccountStatus.ACTIVE
        role = db_session.scalar(select(Role).where(Role.name == "COORDINATOR"))
        if role:
            has_role = db_session.scalar(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
            if not has_role:
                db_session.add(UserRole(user_id=user.id, role_id=role.id))
        db_session.commit()
    return user


@pytest.fixture
def test_user(coordinator_user: User) -> User:
    """Convenience alias for coordinator_user."""
    return coordinator_user


@pytest.fixture
def auth_headers_admin(db_session: Session, admin_user: User) -> Dict[str, str]:
    """Provides Authorization headers with an active session for admin_user."""
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=admin_user.username, password="AdminPass@123")
    db_session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


@pytest.fixture
def auth_headers_user(db_session: Session, regular_user: User) -> Dict[str, str]:
    """Provides Authorization headers with an active session for regular_user."""
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=regular_user.username, password="VolunteerPass@123")
    db_session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


@pytest.fixture
def auth_headers_coordinator(db_session: Session, coordinator_user: User) -> Dict[str, str]:
    """Provides Authorization headers with an active session for coordinator_user."""
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=coordinator_user.username, password="CoordPass@123")
    db_session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


@pytest.fixture
def admin_token(db_session: Session, admin_user: User) -> str:
    """Raw session token for admin."""
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=admin_user.username, password="AdminPass@123")
    db_session.commit()
    return raw_token


@pytest.fixture
def auth_token(db_session: Session, coordinator_user: User) -> str:
    """Raw session token for coordinator."""
    auth_service = AuthService(db_session)
    _, _, raw_token = auth_service.login(username=coordinator_user.username, password="CoordPass@123")
    db_session.commit()
    return raw_token
