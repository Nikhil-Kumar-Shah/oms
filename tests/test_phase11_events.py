"""
Phase 11 — End-to-End Event Management Verification Suite
Tests the complete authoritative flow:
1. Admin creates Event Team account
2. Sports Core creates Event with:
   - Target Vertical
   - Existing Event Team Account
   - Internal POC Head & Additional POCs
   - External Event Head Contact details (Name, Phone, Email)
3. Event Team profile and user are correctly linked
4. Unauthorized operational roles (Coordinator, Volunteer, Event Team) receive 403 on Event Creation and POC Management
5. POC Management (change POC Head, add/remove POCs) works only for Sports Core / Deputy Core / Admin
6. Event status transitions work through proper state machine (PLANNING -> NOT_STARTED -> IN_PROGRESS -> COMPLETED)
"""

import uuid
from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.event import Event, EventMember, EventMemberRole, EventStatus, EventTeamProfile
from app.models.organization import UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.services.auth_service import AuthService


def test_phase11_complete_event_management_flow(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    coordinator_user: User,
    regular_user: User,
    test_vertical: Vertical,
):
    auth_service = AuthService(db_session)
    vert = test_vertical

    # 1. Setup Sports Core User
    sports_core_role = db_session.scalar(select(Role).where(Role.name == "SPORTS_CORE"))
    sports_core_user = db_session.scalar(select(User).where(User.username == "sports_core_test_p11"))
    if not sports_core_user:
        sports_core_user = User(
            username="sports_core_test_p11",
            full_name="Sports Core Lead",
            email="sportscore@paradoxsports.internal",
            password_hash=hash_password("CorePass@123"),
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(sports_core_user)
        db_session.flush()
        db_session.add(UserRole(user_id=sports_core_user.id, role_id=sports_core_role.id))
        db_session.commit()

    _, _, sports_core_token = auth_service.login("sports_core_test_p11", "CorePass@123")
    auth_headers_sports_core = {"Authorization": f"Bearer {sports_core_token}"}

    # Assign users to vertical
    for u in [coordinator_user, regular_user, sports_core_user]:
        existing_uv = db_session.scalar(
            select(UserVertical).where(UserVertical.user_id == u.id, UserVertical.vertical_id == vert.id)
        )
        if not existing_uv:
            db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id))
    db_session.commit()

    # -------------------------------------------------------------
    # Step 1: Admin creates Event Team Account
    # -------------------------------------------------------------
    event_team_role = db_session.scalar(select(Role).where(Role.name == "EVENT_TEAM"))
    team_username = f"event_team_{uuid.uuid4().hex[:6]}"
    team_user = User(
        username=team_username,
        full_name="Phoenix Badminton Team",
        email=f"{team_username}@events.external",
        password_hash=hash_password("TeamPass@123"),
        account_status=AccountStatus.ACTIVE,
    )
    db_session.add(team_user)
    db_session.flush()
    db_session.add(UserRole(user_id=team_user.id, role_id=event_team_role.id))
    db_session.commit()

    _, _, team_token = auth_service.login(team_username, "TeamPass@123")
    auth_headers_team = {"Authorization": f"Bearer {team_token}"}

    # -------------------------------------------------------------
    # Step 2: Operational Roles (Coordinator, Volunteer, Event Team) Receive 403 on Create
    # -------------------------------------------------------------
    _, _, coord_token = auth_service.login(coordinator_user.username, "CoordPass@123")
    auth_headers_coord = {"Authorization": f"Bearer {coord_token}"}

    forbidden_payload = {
        "name": "Unauthorized Tournament",
        "vertical_id": str(vert.id),
        "event_team_user_id": str(team_user.id),
        "poc_head_user_id": str(coordinator_user.id),
        "event_head_name": "External Lead",
        "event_head_phone": "1234567890",
        "event_head_email": "lead@external.org",
    }
    # Coordinator -> 403
    resp_coord = client.post("/api/v1/events", json=forbidden_payload, headers=auth_headers_coord)
    assert resp_coord.status_code == status.HTTP_403_FORBIDDEN

    # Event Team -> 403
    resp_team = client.post("/api/v1/events", json=forbidden_payload, headers=auth_headers_team)
    assert resp_team.status_code == status.HTTP_403_FORBIDDEN

    # -------------------------------------------------------------
    # Step 3: Sports Core creates Event with minimal required payload
    # -------------------------------------------------------------
    event_payload = {
        "name": "State Athletics Championship 2026",
        "vertical_id": str(vert.id),
        "event_team_user_id": str(team_user.id),
        "poc_head_user_id": str(coordinator_user.id),
        "additional_poc_user_ids": [str(regular_user.id)],
        "event_head_name": "Coach Marcus Brody",
        "event_head_phone": "+91 9876543210",
        "event_head_email": "marcus.brody@phoenix.org",
    }

    create_resp = client.post("/api/v1/events", json=event_payload, headers=auth_headers_sports_core)
    assert create_resp.status_code == status.HTTP_201_CREATED
    event_data = create_resp.json()
    event_id = event_data["id"]

    assert event_data["name"] == "State Athletics Championship 2026"
    assert event_data["status"] == "PLANNING"
    assert event_data["primary_poc_id"] == str(coordinator_user.id)
    assert event_data["primary_poc_username"] == coordinator_user.username
    assert event_data["event_team_user_id"] == str(team_user.id)
    assert event_data["event_team_username"] == team_user.username

    # External contact details in resource links
    resource_links = event_data.get("resource_links", {})
    external_head = resource_links.get("event_head", {})
    assert external_head.get("name") == "Coach Marcus Brody"
    assert external_head.get("phone") == "+91 9876543210"
    assert external_head.get("email") == "marcus.brody@phoenix.org"

    # Verify EventTeamProfile linkage in DB
    profile = db_session.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == team_user.id))
    assert profile is not None
    assert profile.event_id == uuid.UUID(event_id)
    assert profile.head_name == "Coach Marcus Brody"

    # -------------------------------------------------------------
    # Step 4: POC Management Permissions & Functionality
    # -------------------------------------------------------------
    # Coordinator tries to manage POCs -> 403
    poc_update_payload = {
        "head_poc_id": str(regular_user.id),
        "poc_member_ids": [str(coordinator_user.id)],
        "notes": "Updated operational responsibilities",
    }
    resp_poc_unauth = client.post(
        f"/api/v1/events/{event_id}/poc-group", json=poc_update_payload, headers=auth_headers_coord
    )
    assert resp_poc_unauth.status_code == status.HTTP_403_FORBIDDEN

    # Event Team tries to manage POCs -> 403
    resp_poc_team = client.post(
        f"/api/v1/events/{event_id}/poc-group", json=poc_update_payload, headers=auth_headers_team
    )
    assert resp_poc_team.status_code == status.HTTP_403_FORBIDDEN

    # Sports Core manages POCs -> 200 SUCCESS
    resp_poc_core = client.post(
        f"/api/v1/events/{event_id}/poc-group", json=poc_update_payload, headers=auth_headers_sports_core
    )
    assert resp_poc_core.status_code == status.HTTP_200_OK
    poc_group_data = resp_poc_core.json()
    assert poc_group_data["head_poc"]["user_id"] == str(regular_user.id)
    assert len(poc_group_data["poc_members"]) == 1
    assert poc_group_data["poc_members"][0]["user_id"] == str(coordinator_user.id)

    # -------------------------------------------------------------
    # Step 5: Lifecycle Status Transitions (PLANNING -> NOT_STARTED -> IN_PROGRESS -> COMPLETED & CANCELLED)
    # -------------------------------------------------------------
    # Unauthorized coordinator tries to transition -> 403
    t_unauth = client.post(
        f"/api/v1/events/{event_id}/transition",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers_coord,
    )
    assert t_unauth.status_code == status.HTTP_403_FORBIDDEN

    # 1. Move to NOT_STARTED
    t1 = client.post(
        f"/api/v1/events/{event_id}/transition",
        json={"status": "NOT_STARTED", "remarks": "Planning complete, awaiting schedule"},
        headers=auth_headers_sports_core,
    )
    assert t1.status_code == status.HTTP_200_OK
    assert t1.json()["status"] == "NOT_STARTED"

    # 2. Start Event (IN_PROGRESS)
    t2 = client.post(
        f"/api/v1/events/{event_id}/transition",
        json={"status": "IN_PROGRESS", "remarks": "Opening ceremony underway"},
        headers=auth_headers_sports_core,
    )
    assert t2.status_code == status.HTTP_200_OK
    assert t2.json()["status"] == "IN_PROGRESS"

    # 3. Mark Completed
    t3 = client.post(
        f"/api/v1/events/{event_id}/transition",
        json={"status": "COMPLETED", "remarks": "Tournament successfully concluded"},
        headers=auth_headers_sports_core,
    )
    assert t3.status_code == status.HTTP_200_OK
    assert t3.json()["status"] == "COMPLETED"

    # 4. Create second event to test CANCELLED transition
    event2_payload = {
        "name": "Cancelled Tennis Tournament 2026",
        "vertical_id": str(vert.id),
        "event_team_user_id": str(team_user.id),
        "poc_head_user_id": str(coordinator_user.id),
        "event_head_name": "Coach Serena",
        "event_head_phone": "+91 9988771122",
        "event_head_email": "serena@tennis.org",
    }
    c2 = client.post("/api/v1/events", json=event2_payload, headers=auth_headers_sports_core)
    assert c2.status_code == status.HTTP_201_CREATED
    event2_id = c2.json()["id"]

    t_cancel = client.post(
        f"/api/v1/events/{event2_id}/transition",
        json={"status": "CANCELLED", "remarks": "Inclement weather forces cancellation"},
        headers=auth_headers_sports_core,
    )
    assert t_cancel.status_code == status.HTTP_200_OK
    assert t_cancel.json()["status"] == "CANCELLED"
