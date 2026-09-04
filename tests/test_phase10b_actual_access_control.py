"""
Phase 10B Actual Role Access & Vertical Data Isolation Test Suite
Validates that API endpoints return strictly authorized scoped data and enforce 403 on unauthorized mutations/resources.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.communication import CommunicationLog, CommunicationLogStatus, CommunicationType
from app.models.event import Event, EventStatus, EventType
from app.models.faq import FAQ, FAQStatus
from app.models.meeting import Meeting, MeetingStatus, MeetingType
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.requirement import Requirement, RequirementPriority, RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.user import AccountStatus, User
from app.services.auth_service import AuthService


def _create_user(
    db: Session,
    username: str,
    role_name: str,
    verticals: list = None,
    password: str = "TestPass@123",
) -> User:
    u = User(
        username=f"{username}_{uuid.uuid4().hex[:6]}",
        full_name=f"Test {username}",
        email=f"{username}_{uuid.uuid4().hex[:6]}@test.internal",
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
def vert_empty(db_session: Session, org: Organization) -> Vertical:
    v = Vertical(
        organization_id=org.id,
        name=f"Vert_Empty_{uuid.uuid4().hex[:6]}",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add(v)
    db_session.commit()
    return v


# -----------------------------------------------------------------------------
# 1. User Directory Authorization & Scoping
# -----------------------------------------------------------------------------

def test_super_coordinator_user_directory_scoped_to_own_vertical(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Super Coordinator A sees only users in Vertical A; Vertical B users are excluded."""
    super_coord_a = _create_user(db_session, "super_a", "SUPER_COORDINATOR", [vert_a])
    coord_a = _create_user(db_session, "coord_a", "COORDINATOR", [vert_a])
    vol_a = _create_user(db_session, "vol_a", "VOLUNTEER", [vert_a])

    super_coord_b = _create_user(db_session, "super_b", "SUPER_COORDINATOR", [vert_b])
    coord_b = _create_user(db_session, "coord_b", "COORDINATOR", [vert_b])

    headers_a = _get_auth_headers(db_session, super_coord_a)

    response = client.get("/api/v1/admin/users", headers=headers_a)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    returned_usernames = [u["username"] for u in data["items"]]

    # Assert users in Vertical A are present
    assert super_coord_a.username in returned_usernames
    assert coord_a.username in returned_usernames
    assert vol_a.username in returned_usernames

    # Assert users in Vertical B are strictly excluded
    assert super_coord_b.username not in returned_usernames
    assert coord_b.username not in returned_usernames


def test_super_coordinator_cannot_view_unrelated_user_detail(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Super Coordinator A cannot fetch detail of User in Vertical B directly by UUID."""
    super_coord_a = _create_user(db_session, "super_a_dir", "SUPER_COORDINATOR", [vert_a])
    coord_b = _create_user(db_session, "coord_b_dir", "COORDINATOR", [vert_b])

    headers_a = _get_auth_headers(db_session, super_coord_a)

    response = client.get(f"/api/v1/admin/users/{coord_b.id}", headers=headers_a)
    assert response.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# 2. Operational Dashboard Scoping
# -----------------------------------------------------------------------------

def test_super_coordinator_empty_vertical_dashboard_produces_zeros(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_empty: Vertical
):
    """A Super Coordinator assigned to an empty vertical sees 0s and not global counts."""
    # Seed data in Vertical A
    admin_user = _create_user(db_session, "admin_user_dash", "ADMIN")
    coord_a = _create_user(db_session, "coord_a_dash", "COORDINATOR", [vert_a])

    # Add tasks in Vertical A
    for i in range(3):
        task = Task(
            vertical_id=vert_a.id,
            assigned_to_id=coord_a.id,
            assigned_by_id=admin_user.id,
            title=f"Task in Vert A {i}",
            task_type=TaskType.ROUTINE,
            priority=TaskPriority.HIGH,
            status=TaskStatus.IN_PROGRESS,
            completion_percentage=25,
            date_assigned=datetime.now(timezone.utc),
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        )
        db_session.add(task)
    db_session.commit()

    # Create Super Coordinator with vert_empty
    super_empty = _create_user(db_session, "super_empty", "SUPER_COORDINATOR", [vert_empty])
    headers_empty = _get_auth_headers(db_session, super_empty)

    response = client.get("/api/v1/analytics/dashboard", headers=headers_empty)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Must legitimately be 0, not leaking the 3 tasks from Vertical A
    assert data["active_tasks"] == 0
    assert data["completed_tasks"] == 0
    assert data["open_issues"] == 0
    assert data["pending_requirements"] == 0


# -----------------------------------------------------------------------------
# 3. FAQ Mutation Enforcement
# -----------------------------------------------------------------------------

def test_faq_update_authorization_rules(
    client: TestClient, db_session: Session, vert_a: Vertical
):
    """
    FAQ Update / Mutation:
    Allowed: ADMIN, SPORTS_CORE, DEPUTY_CORE
    Forbidden: SUPER_COORDINATOR, COORDINATOR, VOLUNTEER, EVENT_TEAM
    """
    admin = _create_user(db_session, "admin_faq", "ADMIN")
    sports_core = _create_user(db_session, "sports_core_faq", "SPORTS_CORE", [vert_a])
    deputy_core = _create_user(db_session, "deputy_core_faq", "DEPUTY_CORE", [vert_a])
    super_coord = _create_user(db_session, "super_coord_faq", "SUPER_COORDINATOR", [vert_a])
    coord = _create_user(db_session, "coord_faq", "COORDINATOR", [vert_a])
    volunteer = _create_user(db_session, "volunteer_faq", "VOLUNTEER", [vert_a])
    event_team = _create_user(db_session, "event_team_faq", "EVENT_TEAM")

    faq = FAQ(
        question="How to log attendance?",
        answer="Use the meeting module.",
        category="General",
        status=FAQStatus.PUBLISHED,
        created_by_id=admin.id,
    )
    db_session.add(faq)
    db_session.commit()

    update_payload = {"question": "How to log operational attendance updated?"}

    # 1. Admin allowed
    res_admin = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, admin))
    assert res_admin.status_code == status.HTTP_200_OK

    # 2. Sports Core allowed
    res_sc = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, sports_core))
    assert res_sc.status_code == status.HTTP_200_OK

    # 3. Deputy Core allowed
    res_dc = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, deputy_core))
    assert res_dc.status_code == status.HTTP_200_OK

    # 4. Super Coordinator forbidden (403)
    res_super = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, super_coord))
    assert res_super.status_code == status.HTTP_403_FORBIDDEN

    # 5. Coordinator forbidden (403)
    res_c = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, coord))
    assert res_c.status_code == status.HTTP_403_FORBIDDEN

    # 6. Volunteer forbidden (403)
    res_v = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, volunteer))
    assert res_v.status_code == status.HTTP_403_FORBIDDEN

    # 7. Event Team forbidden (403)
    res_et = client.patch(f"/api/v1/faqs/{faq.id}", json=update_payload, headers=_get_auth_headers(db_session, event_team))
    assert res_et.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# 4. Official Communication Log Access
# -----------------------------------------------------------------------------

def test_official_communication_log_authorization_rules(
    client: TestClient, db_session: Session, vert_a: Vertical
):
    """
    Official Communication Log:
    Allowed: ADMIN, SPORTS_CORE, DEPUTY_CORE
    Forbidden: SUPER_COORDINATOR, COORDINATOR, VOLUNTEER, EVENT_TEAM
    """
    admin = _create_user(db_session, "admin_comm", "ADMIN")
    sports_core = _create_user(db_session, "sc_comm", "SPORTS_CORE", [vert_a])
    deputy_core = _create_user(db_session, "dc_comm", "DEPUTY_CORE", [vert_a])
    super_coord = _create_user(db_session, "super_comm", "SUPER_COORDINATOR", [vert_a])
    coord = _create_user(db_session, "coord_comm", "COORDINATOR", [vert_a])
    volunteer = _create_user(db_session, "vol_comm", "VOLUNTEER", [vert_a])

    # 1. Admin allowed
    res_admin = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, admin))
    assert res_admin.status_code == status.HTTP_200_OK

    # 2. Sports Core allowed
    res_sc = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, sports_core))
    assert res_sc.status_code == status.HTTP_200_OK

    # 3. Deputy Core allowed
    res_dc = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, deputy_core))
    assert res_dc.status_code == status.HTTP_200_OK

    # 4. Super Coordinator forbidden (403)
    res_super = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, super_coord))
    assert res_super.status_code == status.HTTP_403_FORBIDDEN

    # 5. Coordinator forbidden (403)
    res_c = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, coord))
    assert res_c.status_code == status.HTTP_403_FORBIDDEN

    # 6. Volunteer forbidden (403)
    res_v = client.get("/api/v1/communications", headers=_get_auth_headers(db_session, volunteer))
    assert res_v.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# 5. Master Tasks Endpoint Access
# -----------------------------------------------------------------------------

def test_master_tasks_register_access_rules(
    client: TestClient, db_session: Session, vert_a: Vertical
):
    """
    Master Tasks Global Register (GET /api/v1/tasks):
    Allowed: SPORTS_CORE, DEPUTY_CORE, ADMIN
    Forbidden: SUPER_COORDINATOR, COORDINATOR, VOLUNTEER
    """
    admin = _create_user(db_session, "admin_mt", "ADMIN")
    sports_core = _create_user(db_session, "sc_mt", "SPORTS_CORE", [vert_a])
    deputy_core = _create_user(db_session, "dc_mt", "DEPUTY_CORE", [vert_a])
    super_coord = _create_user(db_session, "super_mt", "SUPER_COORDINATOR", [vert_a])
    coord = _create_user(db_session, "coord_mt", "COORDINATOR", [vert_a])
    volunteer = _create_user(db_session, "vol_mt", "VOLUNTEER", [vert_a])

    # 1. Admin allowed
    res_admin = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, admin))
    assert res_admin.status_code == status.HTTP_200_OK

    # 2. Sports Core allowed
    res_sc = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, sports_core))
    assert res_sc.status_code == status.HTTP_200_OK

    # 3. Deputy Core allowed
    res_dc = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, deputy_core))
    assert res_dc.status_code == status.HTTP_200_OK

    # 4. Super Coordinator forbidden (403)
    res_super = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, super_coord))
    assert res_super.status_code == status.HTTP_403_FORBIDDEN

    # 5. Coordinator forbidden (403)
    res_c = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, coord))
    assert res_c.status_code == status.HTTP_403_FORBIDDEN

    # 6. Volunteer forbidden (403)
    res_v = client.get("/api/v1/tasks", headers=_get_auth_headers(db_session, volunteer))
    assert res_v.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# 6. Cross-Vertical Resource Isolation
# -----------------------------------------------------------------------------

def test_super_coordinator_cross_vertical_task_and_meeting_blocked(
    client: TestClient, db_session: Session, vert_a: Vertical, vert_b: Vertical
):
    """Super Coordinator A cannot access Task or Meeting in Vertical B directly by ID."""
    super_coord_a = _create_user(db_session, "super_a_iso", "SUPER_COORDINATOR", [vert_a])
    coord_b = _create_user(db_session, "coord_b_iso", "COORDINATOR", [vert_b])
    admin = _create_user(db_session, "admin_iso", "ADMIN")

    # Create task in Vertical B
    task_b = Task(
        vertical_id=vert_b.id,
        assigned_to_id=coord_b.id,
        assigned_by_id=admin.id,
        title="Vertical B Task",
        task_type=TaskType.ROUTINE,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        completion_percentage=50,
        date_assigned=datetime.now(timezone.utc),
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add(task_b)

    # Create meeting in Vertical B
    meeting_b = Meeting(
        title="Vertical B Sync",
        meeting_type=MeetingType.VERTICAL_REVIEW,
        meeting_date=date.today() + timedelta(days=1),
        start_time=time(10, 0),
        end_time=time(11, 0),
        location="Room 101",
        vertical_id=vert_b.id,
        organizer_id=coord_b.id,
        status=MeetingStatus.SCHEDULED,
    )

    db_session.add(meeting_b)
    db_session.commit()

    headers_a = _get_auth_headers(db_session, super_coord_a)

    # Super Coordinator A accessing Vertical B Task -> 403
    res_task = client.get(f"/api/v1/tasks/{task_b.id}", headers=headers_a)
    assert res_task.status_code == status.HTTP_403_FORBIDDEN

    # Super Coordinator A accessing Vertical B Meeting -> 403
    res_meeting = client.get(f"/api/v1/meetings/{meeting_b.id}", headers=headers_a)
    assert res_meeting.status_code == status.HTTP_403_FORBIDDEN
