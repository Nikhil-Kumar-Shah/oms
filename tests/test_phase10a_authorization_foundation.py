"""
Phase 10A Authorization Foundation Test Suite
Validates backend authorization rules, role hierarchy direction, vertical scope isolation,
object-level authorization, event team separation, and administrative role boundaries.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import ForbiddenException, ValidationException
from app.core.security import hash_password
from app.models.event import Event, EventMember, EventMemberRole, EventStatus, EventType
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.requirement import Requirement, RequirementPriority, RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.services.authority_service import AuthorityService


# Helper fixtures for Phase 10A
@pytest.fixture
def test_org(db_session: Session) -> Organization:
    stmt = select(Organization).where(Organization.code == "PARADOX_SPORTS")
    org = db_session.scalar(stmt)
    if not org:
        org = Organization(name="Paradox Sports", code="PARADOX_SPORTS")
        db_session.add(org)
        db_session.flush()
    return org


@pytest.fixture
def vertical_a(db_session: Session, test_org: Organization) -> Vertical:
    v = Vertical(
        organization_id=test_org.id,
        name=f"Vertical_Alpha_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def vertical_b(db_session: Session, test_org: Organization) -> Vertical:
    v = Vertical(
        organization_id=test_org.id,
        name=f"Vertical_Beta_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.flush()
    return v


def _create_user_with_role(
    db: Session,
    username: str,
    role_name: str,
    verticals: list = None,
) -> User:
    u = User(
        username=f"{username}_{uuid.uuid4().hex[:6]}",
        full_name=f"Test {username}",
        password_hash=hash_password("Pass@123456"),
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

    db.flush()
    return u


# -----------------------------------------------------------------------------
# 1. Role Hierarchy Tests
# -----------------------------------------------------------------------------

def test_role_hierarchy_downward_allowed(db_session: Session, vertical_a: Vertical):
    """Verifies that authority flows strictly downward."""
    auth_service = AuthorityService(db_session)

    sports_core = _create_user_with_role(db_session, "sports_core_user", "SPORTS_CORE", [vertical_a])
    deputy_core = _create_user_with_role(db_session, "deputy_core_user", "DEPUTY_CORE", [vertical_a])
    super_coord = _create_user_with_role(db_session, "super_coord_user", "SUPER_COORDINATOR", [vertical_a])
    coord = _create_user_with_role(db_session, "coord_user", "COORDINATOR", [vertical_a])
    volunteer = _create_user_with_role(db_session, "volunteer_user", "VOLUNTEER", [vertical_a])

    # Sports Core -> Deputy Core (allowed)
    assert auth_service.can_act_on_user(sports_core, deputy_core) is True

    # Sports Core -> Super Coordinator (allowed)
    assert auth_service.can_act_on_user(sports_core, super_coord) is True

    # Sports Core -> Coordinator (allowed)
    assert auth_service.can_act_on_user(sports_core, coord) is True

    # Sports Core -> Volunteer (allowed)
    assert auth_service.can_act_on_user(sports_core, volunteer) is True

    # Deputy Core -> Super Coordinator (allowed)
    assert auth_service.can_act_on_user(deputy_core, super_coord) is True

    # Deputy Core -> Coordinator (allowed)
    assert auth_service.can_act_on_user(deputy_core, coord) is True

    # Super Coordinator -> Coordinator (same vertical) (allowed)
    assert auth_service.can_act_on_user(super_coord, coord) is True

    # Coordinator -> Volunteer (same vertical) (allowed)
    assert auth_service.can_act_on_user(coord, volunteer) is True


def test_role_hierarchy_upward_denied(db_session: Session, vertical_a: Vertical):
    """Verifies that upward authority actions are strictly rejected with ForbiddenException."""
    auth_service = AuthorityService(db_session)

    sports_core = _create_user_with_role(db_session, "sports_core_up", "SPORTS_CORE", [vertical_a])
    deputy_core = _create_user_with_role(db_session, "deputy_core_up", "DEPUTY_CORE", [vertical_a])
    super_coord = _create_user_with_role(db_session, "super_coord_up", "SUPER_COORDINATOR", [vertical_a])
    coord = _create_user_with_role(db_session, "coord_up", "COORDINATOR", [vertical_a])
    volunteer = _create_user_with_role(db_session, "volunteer_up", "VOLUNTEER", [vertical_a])

    # Deputy Core -> Sports Core (denied)
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(deputy_core, sports_core)
    assert "Hierarchical violation" in str(exc.value)

    # Super Coordinator -> Deputy Core (denied)
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(super_coord, deputy_core)
    assert "Hierarchical violation" in str(exc.value)

    # Coordinator -> Super Coordinator (denied)
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(coord, super_coord)
    assert "Hierarchical violation" in str(exc.value)

    # Volunteer -> Coordinator (denied)
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(volunteer, coord)
    assert "Hierarchical violation" in str(exc.value)


# -----------------------------------------------------------------------------
# 2. Vertical Isolation Tests
# -----------------------------------------------------------------------------

def test_vertical_isolation_foundation(
    db_session: Session,
    vertical_a: Vertical,
    vertical_b: Vertical,
):
    """Verifies vertical isolation rules between non-executive roles."""
    auth_service = AuthorityService(db_session)

    super_coord_a = _create_user_with_role(db_session, "super_a", "SUPER_COORDINATOR", [vertical_a])
    coord_a = _create_user_with_role(db_session, "coord_a", "COORDINATOR", [vertical_a])
    coord_b = _create_user_with_role(db_session, "coord_b", "COORDINATOR", [vertical_b])
    volunteer_b = _create_user_with_role(db_session, "vol_b", "VOLUNTEER", [vertical_b])

    # Super Coordinator A acting on same-vertical target Coordinator A -> Allowed
    assert auth_service.can_act_on_user(super_coord_a, coord_a) is True

    # Super Coordinator A acting on unrelated Vertical B target Coordinator B -> Denied
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(super_coord_a, coord_b)
    assert "Cross-vertical violation" in str(exc.value)

    # Coordinator A acting on unrelated Vertical B Volunteer B -> Denied
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(coord_a, volunteer_b)
    assert "Cross-vertical violation" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Self Access & Assignment Direction Tests
# -----------------------------------------------------------------------------

def test_self_access_and_self_task_creation(db_session: Session, vertical_a: Vertical):
    """Verifies that all roles, including Volunteers, can access self and self-assign tasks."""
    auth_service = AuthorityService(db_session)

    volunteer = _create_user_with_role(db_session, "vol_self", "VOLUNTEER", [vertical_a])
    coord = _create_user_with_role(db_session, "coord_self", "COORDINATOR", [vertical_a])

    # Volunteer acting on self -> Allowed
    assert auth_service.can_act_on_user(volunteer, volunteer) is True
    assert auth_service.can_assign_task(volunteer, volunteer, vertical_a.id) is True

    # Coordinator acting on self -> Allowed
    assert auth_service.can_act_on_user(coord, coord) is True
    assert auth_service.can_assign_task(coord, coord, vertical_a.id) is True

    # Volunteer assigning task to another volunteer -> Denied
    other_vol = _create_user_with_role(db_session, "vol_other", "VOLUNTEER", [vertical_a])
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_assign_task(volunteer, other_vol, vertical_a.id)
    assert "Volunteers may only create self-assigned tasks" in str(exc.value)


def test_assignment_direction_rules(
    db_session: Session,
    vertical_a: Vertical,
    vertical_b: Vertical,
):
    """Verifies task assignment rules enforce downward delegation and vertical matching."""
    auth_service = AuthorityService(db_session)

    sports_core = _create_user_with_role(db_session, "core_assign", "SPORTS_CORE", [vertical_a])
    coord_a = _create_user_with_role(db_session, "coord_assign_a", "COORDINATOR", [vertical_a])
    vol_a = _create_user_with_role(db_session, "vol_assign_a", "VOLUNTEER", [vertical_a])
    vol_b = _create_user_with_role(db_session, "vol_assign_b", "VOLUNTEER", [vertical_b])

    # Coordinator A -> Volunteer A (same vertical) -> Allowed
    assert auth_service.can_assign_task(coord_a, vol_a, vertical_a.id) is True

    # Coordinator A -> Volunteer B (cross vertical) -> Denied
    with pytest.raises(ForbiddenException):
        auth_service.can_assign_task(coord_a, vol_b, vertical_b.id)

    # Sports Core (Executive) -> Volunteer B in Vertical B -> Allowed
    assert auth_service.can_assign_task(sports_core, vol_b, vertical_b.id) is True


# -----------------------------------------------------------------------------
# 4. Object-Level Authorization Tests (Prevent IDOR / BOLA)
# -----------------------------------------------------------------------------

def test_object_level_authorization(
    db_session: Session,
    vertical_a: Vertical,
    vertical_b: Vertical,
):
    """Verifies object-level checks prevent IDOR / BOLA access across vertical boundaries."""
    auth_service = AuthorityService(db_session)

    coord_a = _create_user_with_role(db_session, "coord_obj_a", "COORDINATOR", [vertical_a])
    coord_b = _create_user_with_role(db_session, "coord_obj_b", "COORDINATOR", [vertical_b])

    # Task in Vertical A
    task_a = Task(
        vertical_id=vertical_a.id,
        assigned_by_id=coord_a.id,
        assigned_to_id=coord_a.id,
        title="Task in Vertical Alpha",
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    db_session.add(task_a)

    # Event in Vertical A
    event_a = Event(
        vertical_id=vertical_a.id,
        name="Event in Vertical Alpha",
        event_type=EventType.TOURNAMENT,
        status=EventStatus.PLANNING,
        planned_date="2026-10-15",
        created_by_id=coord_a.id,
    )
    db_session.add(event_a)
    db_session.flush()

    # Coordinator A can access Task A and Event A
    assert auth_service.can_access_object(coord_a, "task", task_a) is True
    assert auth_service.can_access_object(coord_a, "event", event_a) is True

    # Coordinator B (unrelated vertical) CANNOT access Task A or Event A
    assert auth_service.can_access_object(coord_b, "task", task_a) is False
    assert auth_service.can_access_object(coord_b, "event", event_a) is False


# -----------------------------------------------------------------------------
# 5. Event Team Role Separation Tests
# -----------------------------------------------------------------------------

def test_event_team_not_in_internal_hierarchy(db_session: Session, vertical_a: Vertical):
    """Verifies EVENT_TEAM is decoupled from the internal operational hierarchy."""
    auth_service = AuthorityService(db_session)

    event_team_user = _create_user_with_role(db_session, "event_team_user", "EVENT_TEAM")
    volunteer_user = _create_user_with_role(db_session, "vol_ev_test", "VOLUNTEER", [vertical_a])
    coord_user = _create_user_with_role(db_session, "coord_ev_test", "COORDINATOR", [vertical_a])

    # EVENT_TEAM operational level is None
    assert auth_service.get_user_operational_level(event_team_user.id) is None
    assert auth_service.is_internal_operational(event_team_user.id) is False
    assert auth_service.is_event_team(event_team_user.id) is True

    # EVENT_TEAM cannot act on internal users
    with pytest.raises(ForbiddenException):
        auth_service.can_act_on_user(event_team_user, volunteer_user)

    # Internal Coordinator can act on Event Team
    assert auth_service.can_act_on_user(coord_user, event_team_user) is True


# -----------------------------------------------------------------------------
# 6. Admin System Role Separation Tests
# -----------------------------------------------------------------------------

def test_admin_is_separate_from_operational_hierarchy(db_session: Session, vertical_a: Vertical):
    """Verifies ADMIN is a system role decoupled from internal operational levels."""
    auth_service = AuthorityService(db_session)

    admin_user = _create_user_with_role(db_session, "sys_admin", "ADMIN")
    coord_user = _create_user_with_role(db_session, "coord_admin_test", "COORDINATOR", [vertical_a])

    # Admin is not in 1-5 operational hierarchy
    assert auth_service.get_user_operational_level(admin_user.id) is None
    assert auth_service.is_admin(admin_user.id) is True
    assert auth_service.is_internal_operational(admin_user.id) is False

    # Admin can perform administrative user actions
    assert auth_service.can_act_on_user(admin_user, coord_user, action="user_update") is True
    assert auth_service.can_act_on_user(admin_user, coord_user, action="user_reset_password") is True

    # Internal operational users cannot act on Admin
    with pytest.raises(ForbiddenException) as exc:
        auth_service.can_act_on_user(coord_user, admin_user)
    assert "cannot perform authority actions on system administrators" in str(exc.value)
