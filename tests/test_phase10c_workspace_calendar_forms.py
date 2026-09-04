"""
Phase 10C Role-Based Workspace, Event, Forms & Calendar Correction Test Suite
Validates frontend-facing authorization rules, calendar scoping, event creation restrictions,
forms lifecycle, and communication query performance.
"""

import time
import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.calendar import ActivityCategory, CalendarAudience, CalendarEntry, CalendarPriority, CalendarStatus
from app.models.communication import Announcement, AnnouncementPriority, AnnouncementScope, AnnouncementStatus
from app.models.event import Event, EventStatus, EventType
from app.models.faq import FAQ, FAQStatus
from app.models.form import Form, FormAudience, FormFieldType, FormStatus, FormSubmission, FormSubmissionStatus, FormVersion
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.services.auth_service import AuthService
from app.services.workspace_service import WorkspaceService


def _get_auth_headers(db: Session, user: User, password: str = "DevPassword@123") -> dict:
    auth_service = AuthService(db)
    _, _, token = auth_service.login(username=user.username, password=password)
    db.commit()
    return {"Authorization": f"Bearer {token}"}



def _create_user(db: Session, name_prefix: str, role_name: str, verticals: list = None) -> User:
    u = User(
        username=f"{name_prefix}_{uuid.uuid4().hex[:6]}",
        full_name=f"{name_prefix.replace('_', ' ').title()} User",
        email=f"{name_prefix}_{uuid.uuid4().hex[:6]}@paradoxsports.org",
        password_hash=hash_password("DevPassword@123"),
        account_status=AccountStatus.ACTIVE,
    )
    db.add(u)
    db.flush()

    role = db.scalar(select(Role).where(Role.name == role_name))
    if role:
        db.add(UserRole(user_id=u.id, role_id=role.id))

    if verticals:
        for idx, v in enumerate(verticals):
            db.add(UserVertical(user_id=u.id, vertical_id=v.id, is_primary=(idx == 0)))

    db.commit()
    return u


@pytest.fixture
def org_and_verticals(db_session: Session):
    org = Organization(name=f"Paradox Sports {uuid.uuid4().hex[:8]}", code=f"PS_{uuid.uuid4().hex[:8]}".upper())
    db_session.add(org)
    db_session.flush()

    v_tech = Vertical(organization_id=org.id, name=f"Tech_{uuid.uuid4().hex[:6]}", status=VerticalStatus.ACTIVE)
    v_ops = Vertical(organization_id=org.id, name=f"Ops_{uuid.uuid4().hex[:6]}", status=VerticalStatus.ACTIVE)
    db_session.add_all([v_tech, v_ops])
    db_session.commit()
    return org, v_tech, v_ops


# -----------------------------------------------------------------------------
# 1. Event Creation Authorization (SPORTS_CORE/DEPUTY_CORE vs Others)
# -----------------------------------------------------------------------------

def test_event_creation_authorization_rules(client: TestClient, db_session: Session, org_and_verticals):
    org, v_tech, v_ops = org_and_verticals

    sports_core = _create_user(db_session, "sports_core_evt", "SPORTS_CORE", [v_tech])
    deputy_core = _create_user(db_session, "deputy_core_evt", "DEPUTY_CORE", [v_tech])
    super_coord = _create_user(db_session, "super_coord_evt", "SUPER_COORDINATOR", [v_tech])
    coordinator = _create_user(db_session, "coord_evt", "COORDINATOR", [v_tech])
    volunteer = _create_user(db_session, "vol_evt", "VOLUNTEER", [v_tech])

    def _event_payload(name: str):
        return {
            "name": name,
            "vertical_id": str(v_tech.id),
            "event_type": "TOURNAMENT",
            "planned_date": str(date.today() + timedelta(days=10)),
            "location": "Main Stadium",
        }

    # 1. SPORTS_CORE Allowed (201)
    res_sc = client.post("/api/v1/events", json=_event_payload("Sports Core Event"), headers=_get_auth_headers(db_session, sports_core))
    assert res_sc.status_code == status.HTTP_201_CREATED, res_sc.text

    # 2. DEPUTY_CORE Allowed (201)
    res_dc = client.post("/api/v1/events", json=_event_payload("Deputy Core Event"), headers=_get_auth_headers(db_session, deputy_core))
    assert res_dc.status_code == status.HTTP_201_CREATED, res_dc.text

    # 3. SUPER_COORDINATOR Denied (403)
    res_super = client.post("/api/v1/events", json=_event_payload("Super Coord Event"), headers=_get_auth_headers(db_session, super_coord))
    assert res_super.status_code == status.HTTP_403_FORBIDDEN

    # 4. COORDINATOR Denied (403)
    res_coord = client.post("/api/v1/events", json=_event_payload("Coord Event"), headers=_get_auth_headers(db_session, coordinator))
    assert res_coord.status_code == status.HTTP_403_FORBIDDEN

    # 5. VOLUNTEER Denied (403)
    res_vol = client.post("/api/v1/events", json=_event_payload("Vol Event"), headers=_get_auth_headers(db_session, volunteer))
    assert res_vol.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# 2. Master Calendar vs My Calendar Scoping
# -----------------------------------------------------------------------------

def test_master_calendar_vs_my_calendar_scoping(client: TestClient, db_session: Session, org_and_verticals):
    org, v_tech, v_ops = org_and_verticals

    sports_core = _create_user(db_session, "sports_core_cal", "SPORTS_CORE", [v_tech])
    super_coord_tech = _create_user(db_session, "super_tech_cal", "SUPER_COORDINATOR", [v_tech])
    coord_ops = _create_user(db_session, "coord_ops_cal", "COORDINATOR", [v_ops])

    suffix = uuid.uuid4().hex[:6]
    title_tech = f"Tech Deployment {suffix}"
    title_ops = f"Ops Ground Prep {suffix}"
    title_org = f"Annual Sports Gala {suffix}"

    # Entry 1: Tech Vertical Entry
    entry_tech = CalendarEntry(
        title=title_tech,
        activity_date=date.today(),
        category=ActivityCategory.ACTIVITY,
        priority=CalendarPriority.HIGH,
        audience=CalendarAudience.VERTICAL,
        vertical_id=v_tech.id,
        created_by_id=super_coord_tech.id,
    )
    # Entry 2: Ops Vertical Entry
    entry_ops = CalendarEntry(
        title=title_ops,
        activity_date=date.today(),
        category=ActivityCategory.ACTIVITY,
        priority=CalendarPriority.MEDIUM,
        audience=CalendarAudience.VERTICAL,
        vertical_id=v_ops.id,
        created_by_id=coord_ops.id,
    )
    # Entry 3: Organization Wide Entry
    entry_org = CalendarEntry(
        title=title_org,
        activity_date=date.today(),
        category=ActivityCategory.EVENT,
        priority=CalendarPriority.CRITICAL,
        audience=CalendarAudience.ORGANIZATION,
        created_by_id=sports_core.id,
    )
    db_session.add_all([entry_tech, entry_ops, entry_org])
    db_session.commit()

    # 1. SPORTS_CORE (Executive / Master Calendar): receives all entries (Tech, Ops, Org)
    res_sc = client.get(f"/api/v1/calendar?start_date={date.today()}&limit=100", headers=_get_auth_headers(db_session, sports_core))
    assert res_sc.status_code == status.HTTP_200_OK
    sc_titles = [item["title"] for item in res_sc.json()["items"]]
    assert title_tech in sc_titles
    assert title_ops in sc_titles
    assert title_org in sc_titles

    # 2. SUPER_COORDINATOR Tech (My Calendar): receives Tech + Org, but NOT Ops
    res_st = client.get(f"/api/v1/calendar?start_date={date.today()}&limit=100", headers=_get_auth_headers(db_session, super_coord_tech))
    assert res_st.status_code == status.HTTP_200_OK
    st_titles = [item["title"] for item in res_st.json()["items"]]
    assert title_tech in st_titles
    assert title_org in st_titles
    assert title_ops not in st_titles

    # 3. COORDINATOR Ops (My Calendar): receives Ops + Org, but NOT Tech
    res_co = client.get(f"/api/v1/calendar?start_date={date.today()}&limit=100", headers=_get_auth_headers(db_session, coord_ops))
    assert res_co.status_code == status.HTTP_200_OK
    co_titles = [item["title"] for item in res_co.json()["items"]]
    assert title_ops in co_titles
    assert title_org in co_titles

    assert title_tech not in co_titles


# -----------------------------------------------------------------------------
# 3. Dynamic Forms Persistence, Submission, and Review Workflow
# -----------------------------------------------------------------------------

def test_dynamic_forms_end_to_end_lifecycle(client: TestClient, db_session: Session, org_and_verticals):
    org, v_tech, v_ops = org_and_verticals

    admin = _create_user(db_session, "admin_form", "ADMIN")
    super_coord = _create_user(db_session, "super_form", "SUPER_COORDINATOR", [v_tech])
    volunteer = _create_user(db_session, "vol_form", "VOLUNTEER", [v_tech])

    # 1. Admin creates form template with schema
    create_payload = {
        "name": f"Equipment Inspection Form {uuid.uuid4().hex[:6]}",
        "description": "Log broken ground equipment for replacement",
        "purpose": "Logistics equipment replacement",
        "target_audience": "ORGANIZATION",
        "initial_schema": [
            {"key": "equipment_name", "label": "Equipment Name", "type": "TEXT", "required": True, "ordering": 0},
            {"key": "damage_severity", "label": "Damage Severity", "type": "SELECT", "required": True, "options": ["LOW", "MEDIUM", "HIGH"], "ordering": 1},
            {"key": "cost_estimate", "label": "Estimated Cost", "type": "NUMBER", "required": False, "ordering": 2},
        ],
        "transformation_config": {
            "target_entity": "TASK",
            "field_mappings": {"title": "equipment_name", "description": "damage_severity"},
        },
    }
    res_create = client.post("/api/v1/forms", json=create_payload, headers=_get_auth_headers(db_session, admin))
    assert res_create.status_code == status.HTTP_201_CREATED, res_create.text
    form_id = res_create.json()["id"]

    # 2. Publish Version 1
    res_pub = client.post(f"/api/v1/forms/{form_id}/publish?version_number=1", headers=_get_auth_headers(db_session, admin))
    assert res_pub.status_code == status.HTTP_200_OK


    # 3. Volunteer views published form schema
    res_view = client.get(f"/api/v1/forms/{form_id}", headers=_get_auth_headers(db_session, volunteer))
    assert res_view.status_code == status.HTTP_200_OK
    schema_fields = res_view.json()["latest_version"]["schema_fields"]
    assert len(schema_fields) == 3
    assert schema_fields[0]["key"] == "equipment_name"

    # 4. Volunteer submits form response
    submission_payload = {
        "submission_data": {
            "equipment_name": "Corner Flag Post #3",
            "damage_severity": "HIGH",
            "cost_estimate": 45,
        }
    }
    res_submit = client.post(f"/api/v1/forms/{form_id}/submissions", json=submission_payload, headers=_get_auth_headers(db_session, volunteer))
    assert res_submit.status_code == status.HTTP_201_CREATED, res_submit.text
    sub_id = res_submit.json()["id"]

    # 5. Super Coordinator reviews and approves submission with automated conversion
    review_payload = {
        "status": "APPROVED",
        "review_comments": "Approved for immediate equipment replenishment.",
        "execute_transformation": True,
    }
    res_rev = client.post(f"/api/v1/form-submissions/{sub_id}/review", json=review_payload, headers=_get_auth_headers(db_session, super_coord))
    assert res_rev.status_code == status.HTTP_200_OK
    assert res_rev.json()["status"] == "APPROVED"



# -----------------------------------------------------------------------------
# 4. Directives Clean Retirement & Workspace Service Optimization
# -----------------------------------------------------------------------------

def test_workspace_service_runs_cleanly_without_directives(db_session: Session, org_and_verticals):
    org, v_tech, _ = org_and_verticals
    user = _create_user(db_session, "user_mywork", "VOLUNTEER", [v_tech])

    # Invoke workspace service
    my_work = WorkspaceService.get_unified_my_work(db_session, user)
    assert my_work.user_id == user.id
    assert my_work.stats.pending_directives == 0
    assert my_work.pending_directives == []


# -----------------------------------------------------------------------------
# 5. Communication Query Performance (< 1.0 Second Latency)
# -----------------------------------------------------------------------------

def test_communication_and_calendar_query_performance(client: TestClient, db_session: Session, org_and_verticals):
    org, v_tech, _ = org_and_verticals
    admin = _create_user(db_session, "admin_perf", "ADMIN")
    headers = _get_auth_headers(db_session, admin)

    # 1. Announcements list timing
    start_ann = time.perf_counter()
    res_ann = client.get("/api/v1/announcements?limit=50", headers=headers)
    ann_duration = time.perf_counter() - start_ann
    assert res_ann.status_code == status.HTTP_200_OK
    assert ann_duration < 1.0, f"Announcements list took {ann_duration:.3f}s (expected < 1.0s)"

    # 2. Notifications list timing
    start_notif = time.perf_counter()
    res_notif = client.get("/api/v1/notifications?limit=50", headers=headers)
    notif_duration = time.perf_counter() - start_notif
    assert res_notif.status_code == status.HTTP_200_OK
    assert notif_duration < 1.0, f"Notifications list took {notif_duration:.3f}s (expected < 1.0s)"

    # 3. Calendar list timing
    start_cal = time.perf_counter()
    res_cal = client.get("/api/v1/calendar?limit=50", headers=headers)
    cal_duration = time.perf_counter() - start_cal
    assert res_cal.status_code == status.HTTP_200_OK
    assert cal_duration < 1.0, f"Calendar list took {cal_duration:.3f}s (expected < 1.0s)"
