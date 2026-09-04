"""
Phase 10E — Event ↔ Internal Team ↔ External Event Team Integration Test Suite
Paradox Sports OMS - Authorization & Event Integration Verification
"""

import pytest
import uuid
from datetime import date, time
from sqlalchemy import select
from app.models.event import Event, EventMember, EventMemberRole, EventStatus, EventTeamProfile, EventType
from app.models.organization import Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.schemas.event import EventCreate, EventMemberCreate
from app.services.authority_service import AuthorityService
from app.services.event_service import EventService
from app.core.exceptions import ForbiddenException, ValidationException


@pytest.fixture
def phase10e_env(db_session):
    """Sets up a clean test fixture with multi-role users, verticals, and profiles."""
    db = db_session

    from app.models.organization import Organization
    org = db.scalar(select(Organization))
    if not org:
        org = Organization(name="Test Org", code="TEST_ORG")
        db.add(org)
        db.flush()

    # 1. Setup Verticals
    v1 = Vertical(organization_id=org.id, name=f"Cricket Vert {uuid.uuid4().hex[:6]}", status=VerticalStatus.ACTIVE)
    v2 = Vertical(organization_id=org.id, name=f"Football Vert {uuid.uuid4().hex[:6]}", status=VerticalStatus.ACTIVE)
    db.add_all([v1, v2])
    db.flush()

    # 2. Roles
    roles = {r.name: r for r in db.scalars(select(Role)).all()}

    def create_user_with_role(username: str, role_name: str) -> User:
        user = User(
            username=f"{username}_{uuid.uuid4().hex[:6]}",
            email=f"{username}_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy",
            full_name=f"Test {username.title()}",
            account_status=AccountStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=roles[role_name].id))
        db.flush()
        return user

    admin_user = create_user_with_role("admin", "ADMIN")
    sports_core = create_user_with_role("score", "SPORTS_CORE")
    deputy_core = create_user_with_role("dcore", "DEPUTY_CORE")
    super_coord = create_user_with_role("scoord", "SUPER_COORDINATOR")
    coordinator = create_user_with_role("coord", "COORDINATOR")
    volunteer = create_user_with_role("vol", "VOLUNTEER")
    event_team_user = create_user_with_role("evteam", "EVENT_TEAM")

    # Create an initial EventTeamProfile for the event_team_user
    et_profile = EventTeamProfile(
        user_id=event_team_user.id,
        team_name="Phoenix Cricket Club",
        head_name="Original Head",
        head_phone="+1 555-0001",
        head_email="original@phoenix.org",
        members_summary=[],
    )
    db.add(et_profile)
    db.flush()

    return {
        "db": db,
        "v1": v1,
        "v2": v2,
        "admin": admin_user,
        "sports_core": sports_core,
        "deputy_core": deputy_core,
        "super_coord": super_coord,
        "coordinator": coordinator,
        "volunteer": volunteer,
        "event_team_user": event_team_user,
        "event_team_profile": et_profile,
    }


def test_event_creation_role_permissions(phase10e_env):
    """Verifies SPORTS_CORE, DEPUTY_CORE, and ADMIN can create events; non-executives are forbidden."""
    env = phase10e_env
    db = env["db"]
    authority = AuthorityService(db)

    # Executive roles
    assert authority.is_executive_or_admin(env["admin"].id) is True
    assert authority.is_executive(env["sports_core"].id) is True
    assert authority.is_executive(env["deputy_core"].id) is True

    # Non-executives
    assert authority.is_executive(env["super_coord"].id) is False
    assert authority.is_executive(env["coordinator"].id) is False
    assert authority.is_executive(env["volunteer"].id) is False
    assert authority.is_executive(env["event_team_user"].id) is False


def test_atomic_event_creation_with_event_team_and_external_pocs(phase10e_env):
    """
    Verifies that an event is created atomically with:
    1. Associated EVENT_TEAM account.
    2. External Event Head contact info.
    3. Dynamic POCs list stored in members_summary.
    """
    env = phase10e_env
    db = env["db"]
    service = EventService(db)

    pocs = [
        {"name": "Alice Smith", "phone": "+1 555-1111", "email": "alice@phoenix.org", "designation": "Manager"},
        {"name": "Bob Jones", "phone": "+1 555-2222", "email": "bob@phoenix.org", "designation": "Captain"},
    ]

    event_data = EventCreate(
        name="Annual T20 Championship 2026",
        vertical_id=env["v1"].id,
        event_type=EventType.TOURNAMENT,
        planned_date=date(2026, 10, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        location="Main Cricket Ground",
        society_name="Cricket Society",
        description="Annual cricket cup with visiting teams",
        event_team_user_id=env["event_team_user"].id,
        event_head_name="Coach David Miller",
        event_head_phone="+1 555-9999",
        event_head_email="david@phoenix.org",
        additional_pocs=pocs,
    )

    created_event = service.create_event(event_data, actor_id=env["sports_core"].id)
    assert created_event.id is not None
    assert created_event.name == "Annual T20 Championship 2026"
    assert created_event.status == EventStatus.PLANNING

    # Verify EventTeamProfile was updated and linked
    profile = db.scalar(
        select(EventTeamProfile).where(EventTeamProfile.user_id == env["event_team_user"].id)
    )
    assert profile is not None
    assert profile.event_id == created_event.id
    assert profile.head_name == "Coach David Miller"
    assert profile.head_phone == "+1 555-9999"
    assert profile.head_email == "david@phoenix.org"
    assert len(profile.members_summary) == 2
    assert profile.members_summary[0]["name"] == "Alice Smith"
    assert profile.members_summary[1]["name"] == "Bob Jones"


def test_cannot_associate_non_event_team_account(phase10e_env):
    """Verifies that attempting to associate an internal user (e.g. dcore) as event_team_user_id is rejected."""
    env = phase10e_env
    db = env["db"]
    service = EventService(db)

    event_data = EventCreate(
        name="Invalid Event Team Binding",
        vertical_id=env["v1"].id,
        event_type=EventType.MATCH,
        planned_date=date(2026, 11, 1),
        event_team_user_id=env["deputy_core"].id, # Invalid: dcore is DEPUTY_CORE, not EVENT_TEAM
    )

    with pytest.raises(ValidationException) as exc_info:
        service.create_event(event_data, actor_id=env["sports_core"].id)

    assert "does not have the EVENT_TEAM role" in str(exc_info.value)


def test_internal_event_member_cross_vertical_and_hierarchy(phase10e_env):
    """
    Verifies that:
    1. Executive SPORTS_CORE / DEPUTY_CORE can assign internal members without vertical mismatch errors.
    2. Lower-level internal users cannot assign higher-level operators.
    3. External EVENT_TEAM accounts cannot be assigned as internal event operations staff.
    """
    env = phase10e_env
    db = env["db"]
    service = EventService(db)

    # Create event in Vertical 1
    event_data = EventCreate(
        name="Inter-Vertical League",
        vertical_id=env["v1"].id,
        event_type=EventType.TOURNAMENT,
        planned_date=date(2026, 12, 1),
    )
    event = service.create_event(event_data, actor_id=env["sports_core"].id)

    # 1. Sports Core assigns Coordinator and Volunteer (Executive cross-vertical success)
    member_coord = service.add_event_member(
        event_id=event.id,
        data=EventMemberCreate(user_id=env["coordinator"].id, role_in_event=EventMemberRole.COORDINATOR),
        actor_id=env["sports_core"].id,
    )
    assert member_coord.id is not None
    assert member_coord.user_id == env["coordinator"].id

    # 2. Sports Core assigns Deputy Core as Head (Executive assignment success)
    member_dcore = service.add_event_member(
        event_id=event.id,
        data=EventMemberCreate(user_id=env["deputy_core"].id, role_in_event=EventMemberRole.HEAD),
        actor_id=env["sports_core"].id,
    )
    assert member_dcore.id is not None
    assert member_dcore.user_id == env["deputy_core"].id

    # 3. Volunteer cannot assign internal members (ForbiddenException)
    with pytest.raises(ForbiddenException) as exc_info:
        service.add_event_member(
            event_id=event.id,
            data=EventMemberCreate(user_id=env["coordinator"].id, role_in_event=EventMemberRole.COORDINATOR),
            actor_id=env["volunteer"].id,
        )
    assert "Volunteers cannot assign internal staff" in str(exc_info.value)

    # 4. Coordinator cannot assign Deputy Core (Hierarchical upward assignment denied)
    with pytest.raises(ForbiddenException) as exc_info:
        service.add_event_member(
            event_id=event.id,
            data=EventMemberCreate(user_id=env["deputy_core"].id, role_in_event=EventMemberRole.HEAD),
            actor_id=env["coordinator"].id,
        )
    assert "Hierarchical violation" in str(exc_info.value)

    # 5. External EVENT_TEAM account cannot be assigned as internal event operations staff
    with pytest.raises(ValidationException) as exc_info:
        service.add_event_member(
            event_id=event.id,
            data=EventMemberCreate(user_id=env["event_team_user"].id, role_in_event=EventMemberRole.COORDINATOR),
            actor_id=env["sports_core"].id,
        )
    assert "Cannot assign external Event Team accounts as internal event operations staff" in str(exc_info.value)
