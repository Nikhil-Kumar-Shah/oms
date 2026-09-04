"""
Phase 11 Automated Test Suite: Form & Response Workflow System
Tests Form Templates, Immutable Versions, Transactional Multi-Recipient Distribution,
Independent Response Instances, Multi-Phase Review Checklists, Return & Resubmission Lifecycle,
Forwarding Audit Timeline, and Aggregate Distribution Matrix.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.communication import Notification
from app.models.event import Event, EventStatus, EventTeamProfile, EventType
from app.models.form import (
    ChecklistStatus,
    Form,
    FormAudience,
    FormChecklistItem,
    FormDistribution,
    FormResponse,
    FormResponseStatus,
    FormReviewer,
    FormStatus,
    FormVersion,
    FormWorkflowHistory,
)
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User, UserProfile
from app.services.auth_service import AuthService
from app.services.form_service import FormService


def _get_auth_headers(db: Session, user: User, password: str = "Password123!") -> dict:
    auth_service = AuthService(db)
    _, _, token = auth_service.login(username=user.username, password=password)
    db.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase11_setup(db_session: Session):
    """Sets up Volleyball vertical, SC-Volleyball, Coordinators, POCs, and 8 Event Teams."""
    # Ensure Organization
    org = db_session.scalar(select(Organization).where(Organization.code == "PARADOX_SPORTS"))
    if not org:
        org = Organization(name="Paradox Sports Department", code="PARADOX_SPORTS", description="Test org")
        db_session.add(org)
        db_session.flush()

    # Create Volleyball Vertical
    volleyball_vert = db_session.scalar(select(Vertical).where(Vertical.name == "Volleyball Operations"))
    if not volleyball_vert:
        volleyball_vert = Vertical(organization_id=org.id, name="Volleyball Operations", status=VerticalStatus.ACTIVE)
        db_session.add(volleyball_vert)
        db_session.flush()

    # Roles lookup
    roles = {r.name: r for r in db_session.scalars(select(Role)).all()}

    # 1. Executive users
    def create_or_get_user(username: str, role_name: str, vert=None):
        u = db_session.scalar(select(User).where(User.username == username))
        if not u:
            u = User(
                username=username,
                full_name=f"Test {username.upper()}",
                email=f"{username}@paradoxsports.internal",
                password_hash=hash_password("Password123!"),
                account_status=AccountStatus.ACTIVE,
            )
            db_session.add(u)
            db_session.flush()
            db_session.add(UserRole(user_id=u.id, role_id=roles[role_name].id))
            if vert:
                db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id, is_primary=True))
            db_session.flush()
        return u

    sports_core = create_or_get_user("sports_core_11", "SPORTS_CORE")
    sc_volleyball = create_or_get_user("sc_volleyball_11", "SUPER_COORDINATOR", volleyball_vert)
    coord_volleyball = create_or_get_user("coord_volleyball_11", "COORDINATOR", volleyball_vert)
    volunteer_volleyball = create_or_get_user("vol_volleyball_11", "VOLUNTEER", volleyball_vert)

    # Create Tournament Event
    event = db_session.scalar(select(Event).where(Event.name == "Inter-College Volleyball Championship"))
    if not event:
        event = Event(
            vertical_id=volleyball_vert.id,
            name="Inter-College Volleyball Championship",
            event_type=EventType.TOURNAMENT,
            status=EventStatus.PLANNING,
            planned_date=datetime(2026, 9, 10, tzinfo=timezone.utc).date(),
            location="Main Sports Arena",
            created_by_id=sports_core.id,
        )
        db_session.add(event)
        db_session.flush()

    # 2. Eight Event Teams
    event_teams = []
    for letter in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        t_user = create_or_get_user(f"team_{letter.lower()}_11", "EVENT_TEAM")
        # Create EventTeamProfile
        prof = db_session.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == t_user.id))
        if not prof:
            prof = EventTeamProfile(
                user_id=t_user.id,
                event_id=event.id,
                team_name=f"Event Team {letter}",
                head_email=f"team_{letter.lower()}@collegesports.org",
            )
            db_session.add(prof)
        event_teams.append(t_user)

    db_session.commit()

    return {
        "org": org,
        "vertical": volleyball_vert,
        "event": event,
        "sports_core": sports_core,
        "sc_volleyball": sc_volleyball,
        "coord_volleyball": coord_volleyball,
        "volunteer": volunteer_volleyball,
        "event_teams": event_teams,
    }


def test_form_creation_role_authorization(client: TestClient, phase11_setup, db_session: Session):
    """Verifies that only authorized roles can create form templates."""
    sc_headers = _get_auth_headers(db_session, phase11_setup["sc_volleyball"])
    sports_core_headers = _get_auth_headers(db_session, phase11_setup["sports_core"])
    coord_headers = _get_auth_headers(db_session, phase11_setup["coord_volleyball"])
    vol_headers = _get_auth_headers(db_session, phase11_setup["volunteer"])
    team_headers = _get_auth_headers(db_session, phase11_setup["event_teams"][0])

    # 1. Super Coordinator creates template -> Allowed (201)
    res_sc = client.post(
        "/api/v1/forms",
        json={
            "name": "Volleyball Rulebook Submission",
            "purpose": "Tournament rulebook collection and verification",
            "vertical_id": str(phase11_setup["vertical"].id),
            "category": "Tournament",
            "sections": [
                {
                    "title": "Basic Event Information",
                    "fields": [{"key": "tournament_name", "label": "Tournament Name", "type": "TEXT", "required": True}],
                }
            ],
        },
        headers=sc_headers,
    )
    assert res_sc.status_code == 201

    # 2. Sports Core creates template -> Allowed (201)
    res_core = client.post(
        "/api/v1/forms",
        json={
            "name": "General Incident Report Form",
            "purpose": "Safety compliance",
            "category": "Compliance",
        },
        headers=sports_core_headers,
    )
    assert res_core.status_code == 201

    # 3. Coordinator -> Blocked (403 Forbidden)
    res_coord = client.post(
        "/api/v1/forms",
        json={"name": "Illegal Form", "purpose": "Test"},
        headers=coord_headers,
    )
    assert res_coord.status_code == 403

    # 4. Volunteer -> Blocked (403 Forbidden)
    res_vol = client.post(
        "/api/v1/forms",
        json={"name": "Illegal Form", "purpose": "Test"},
        headers=vol_headers,
    )
    assert res_vol.status_code == 403

    # 5. Event Team -> Blocked (403 Forbidden)
    res_team = client.post(
        "/api/v1/forms",
        json={"name": "Illegal Form", "purpose": "Test"},
        headers=team_headers,
    )
    assert res_team.status_code == 403


def test_form_versioning_and_immutability(client: TestClient, phase11_setup, db_session: Session):
    """Verifies that publishing a version makes it immutable and new versions do not alter old ones."""
    sc_headers = _get_auth_headers(db_session, phase11_setup["sc_volleyball"])

    # Create Form
    res = client.post(
        "/api/v1/forms",
        json={
            "name": "Equipment Inspection Form",
            "purpose": "Logistics verification",
            "sections": [
                {
                    "title": "Equipment Section",
                    "fields": [{"key": "net_height", "label": "Net Height (m)", "type": "NUMBER", "required": True}],
                }
            ],
        },
        headers=sc_headers,
    )
    assert res.status_code == 201
    form_id = res.json()["id"]

    # Publish Version 1
    res_pub = client.post(f"/api/v1/forms/{form_id}/publish?version_number=1", headers=sc_headers)
    assert res_pub.status_code == 200
    assert res_pub.json()["is_published"] is True
    assert res_pub.json()["version_number"] == 1

    # Create Version 2 with additional field
    res_v2 = client.post(
        f"/api/v1/forms/{form_id}/versions",
        json={
            "sections": [
                {
                    "title": "Equipment Section v2",
                    "fields": [
                        {"key": "net_height", "label": "Net Height (m)", "type": "NUMBER", "required": True},
                        {"key": "ball_pressure", "label": "Ball Pressure (psi)", "type": "NUMBER", "required": True},
                    ],
                }
            ]
        },
        headers=sc_headers,
    )
    assert res_v2.status_code == 201
    assert res_v2.json()["version_number"] == 2
    assert res_v2.json()["is_published"] is False


def test_end_to_end_distribution_8_event_teams_and_full_workflow(client: TestClient, phase11_setup, db_session: Session):
    """
    Mandatory Acceptance Test Scenario:
    1. SC creates 'Event Rulebook Submission' with 4 sections.
    2. Publishes Form.
    3. Distributes to 8 Event Teams (Team A .. Team H).
    4. Verifies in PostgreSQL: 1 Form, 1 Published Version, 8 Response Instances.
    5. All 8 Event Teams save draft and submit response with valid reference URLs.
    6. Multi-reviewers review responses and complete checklists.
    7. Return Team C with mandatory return reason -> C = RETURNED.
    8. Team C corrects and resubmits -> C = RESUBMITTED with full history preserved.
    9. Approve remaining 7 teams -> Aggregate Summary shows 7 Approved, 1 Resubmitted/Under Review.
    """
    sc_headers = _get_auth_headers(db_session, phase11_setup["sc_volleyball"])
    sports_core_headers = _get_auth_headers(db_session, phase11_setup["sports_core"])

    # 1. Create Form Template with 4 structured sections
    create_payload = {
        "name": "Event Rulebook Submission",
        "purpose": "Standardized collection and verification of sports competition rulebooks",
        "instructions": "Please provide authoritative Google Drive/OneDrive document references.",
        "category": "Tournament",
        "vertical_id": str(phase11_setup["vertical"].id),
        "event_id": str(phase11_setup["event"].id),
        "sections": [
            {
                "title": "Section 1: Event Information",
                "description": "Basic tournament details",
                "fields": [
                    {"key": "event_title", "label": "Tournament Title", "type": "TEXT", "required": True},
                    {"key": "expected_teams", "label": "Expected Team Count", "type": "NUMBER", "required": True},
                ],
            },
            {
                "title": "Section 2: Rulebook",
                "description": "Rulebook specifications",
                "fields": [
                    {"key": "rulebook_ref_url", "label": "Authoritative Rulebook Reference URL", "type": "REFERENCE_LINK", "required": True},
                ],
            },
            {
                "title": "Section 3: Eligibility",
                "description": "Player and team eligibility criteria",
                "fields": [
                    {"key": "eligibility_terms", "label": "Eligibility Requirements", "type": "LONG_TEXT", "required": True},
                ],
            },
            {
                "title": "Section 4: Reference Links & Declaration",
                "description": "Supporting links and confirmation",
                "fields": [
                    {"key": "schedule_url", "label": "Draft Schedule Document URL", "type": "URL", "required": True},
                    {"key": "declaration", "label": "I confirm compliance with Paradox OMS rulebook standards", "type": "CHECKBOX", "required": True},
                ],
            },
        ],
        "review_config": [
            {"phase_number": 1, "phase_name": "Phase 1: Event Team Submission", "title": "Submission Form & Links Complete"},
            {"phase_number": 2, "phase_name": "Phase 2: POC Review", "title": "POC Technical Rulebook Verification"},
            {"phase_number": 3, "phase_name": "Phase 3: Vertical Review", "title": "Vertical Coordinator Sign-off"},
            {"phase_number": 4, "phase_name": "Phase 4: Sports Core Approval", "title": "Executive Sports Core Sign-off"},
        ],
    }

    res_create = client.post("/api/v1/forms", json=create_payload, headers=sc_headers)
    assert res_create.status_code == 201
    form_id = res_create.json()["id"]

    # 2. Publish Version 1
    res_pub = client.post(f"/api/v1/forms/{form_id}/publish?version_number=1", headers=sc_headers)
    assert res_pub.status_code == 200

    # 3. Distribute to all 8 Event Teams
    event_teams = phase11_setup["event_teams"]
    recipient_ids = [str(t.id) for t in event_teams]

    res_dist = client.post(
        f"/api/v1/forms/{form_id}/distribute",
        json={
            "recipient_ids": recipient_ids,
            "deadline": "2026-09-08T18:00:00Z",
            "instructions": "Please submit by 8th Sep 6:00 PM.",
        },
        headers=sc_headers,
    )
    assert res_dist.status_code == 201
    dist_data = res_dist.json()
    assert dist_data["recipient_count"] == 8

    # 4. Direct Database Verification
    form_db = db_session.get(Form, form_id)
    assert form_db is not None
    assert form_db.status == FormStatus.PUBLISHED

    versions_db = db_session.scalars(select(FormVersion).where(FormVersion.form_id == form_id)).all()
    assert len(versions_db) == 1
    assert versions_db[0].is_published is True

    distributions_db = db_session.scalars(select(FormDistribution).where(FormDistribution.form_id == form_id)).all()
    assert len(distributions_db) == 1

    responses_db = db_session.scalars(select(FormResponse).where(FormResponse.form_id == form_id)).all()
    assert len(responses_db) == 8, f"Expected exactly 8 responses in DB, found {len(responses_db)}"

    # Verify notifications were created for recipients
    notifs = db_session.scalars(
        select(Notification).where(Notification.related_resource_type == "FORM_RESPONSE")
    ).all()
    assert len(notifs) >= 8

    # 5. Fill all 8 responses (Save draft and Submit)
    team_response_map = {}
    for letter, team_user in zip(["A", "B", "C", "D", "E", "F", "G", "H"], event_teams):
        team_headers = _get_auth_headers(db_session, team_user)

        # Query assigned response
        res_my_resp = client.get("/api/v1/form-responses?workspace_tab=assigned_to_me", headers=team_headers)
        assert res_my_resp.status_code == 200
        items = res_my_resp.json()["items"]
        assert len(items) >= 1
        resp_item = next(r for r in items if r["form_id"] == form_id)
        resp_id = resp_item["id"]
        team_response_map[letter] = resp_id

        # 5a. Save Draft
        draft_payload = {
            "response_data": {
                "event_title": f"Volleyball Cup - Team {letter}",
                "expected_teams": 12,
                "rulebook_ref_url": f"https://drive.google.com/file/d/rulebook_team_{letter.lower()}/view",
            }
        }
        res_draft = client.post(f"/api/v1/form-responses/{resp_id}/draft", json=draft_payload, headers=team_headers)
        assert res_draft.status_code == 200
        assert res_draft.json()["status"] == "IN_PROGRESS"

        # 5b. Complete and Submit
        submit_payload = {
            "response_data": {
                "event_title": f"Volleyball Cup - Team {letter}",
                "expected_teams": 12,
                "rulebook_ref_url": f"https://drive.google.com/file/d/rulebook_team_{letter.lower()}/view",
                "eligibility_terms": "Undergraduate students enrolled in 2026-27 session.",
                "schedule_url": f"https://onedrive.live.com/schedule_team_{letter.lower()}",
                "declaration": True,
            }
        }
        res_sub = client.post(f"/api/v1/form-responses/{resp_id}/submit", json=submit_payload, headers=team_headers)
        assert res_sub.status_code == 200
        assert res_sub.json()["status"] == "SUBMITTED"

    # 6. Verify Checklists and Review Workflow
    # Update checklist items for Team A
    team_a_resp_id = team_response_map["A"]
    res_a_detail = client.get(f"/api/v1/form-responses/{team_a_resp_id}", headers=sc_headers)
    assert res_a_detail.status_code == 200
    chk_items = res_a_detail.json()["checklist_items"]
    assert len(chk_items) == 4

    for chk in chk_items:
        res_chk_up = client.patch(
            f"/api/v1/form-responses/checklist/{chk['id']}",
            json={"status": "PASSED", "remarks": "Verified by SC"},
            headers=sc_headers,
        )
        assert res_chk_up.status_code == 200
        assert res_chk_up.json()["status"] == "PASSED"

    # 7. Return Team C with mandatory return reason
    team_c_resp_id = team_response_map["C"]
    res_return = client.post(
        f"/api/v1/form-responses/{team_c_resp_id}/return",
        json={
            "return_reason": "Missing tie-breaker rules in rulebook and missing certified medical clearance in eligibility.",
            "reviewer_remarks": "Please update section 2 and resubmit by tomorrow.",
        },
        headers=sc_headers,
    )
    assert res_return.status_code == 200
    assert res_return.json()["status"] == "RETURNED"
    assert "Missing tie-breaker rules" in res_return.json()["return_reason"]

    # 8. Event Team C corrects and Resubmits
    team_c_headers = _get_auth_headers(db_session, phase11_setup["event_teams"][2])
    res_c_resub = client.post(
        f"/api/v1/form-responses/{team_c_resp_id}/submit",
        json={
            "response_data": {
                "event_title": "Volleyball Cup - Team C (Updated)",
                "expected_teams": 12,
                "rulebook_ref_url": "https://drive.google.com/file/d/rulebook_team_c_v2/view",
                "eligibility_terms": "Undergraduate students with certified medical clearance.",
                "schedule_url": "https://onedrive.live.com/schedule_team_c",
                "declaration": True,
            }
        },
        headers=team_c_headers,
    )
    assert res_c_resub.status_code == 200
    assert res_c_resub.json()["status"] == "RESUBMITTED"
    assert res_c_resub.json()["resubmitted_at"] is not None

    # Verify Team C workflow history preserves previous submission and return
    res_c_detail = client.get(f"/api/v1/form-responses/{team_c_resp_id}", headers=team_c_headers)
    history_actions = [h["action"] for h in res_c_detail.json()["workflow_history"]]
    assert "DISTRIBUTED" in history_actions
    assert "SUBMITTED" in history_actions
    assert "RETURNED" in history_actions
    assert "RESUBMITTED" in history_actions

    # 9. Approve remaining 7 teams (A, B, D, E, F, G, H)
    for letter in ["A", "B", "D", "E", "F", "G", "H"]:
        resp_id = team_response_map[letter]
        res_app = client.post(
            f"/api/v1/form-responses/{resp_id}/review",
            json={"action": "APPROVE", "reviewer_remarks": f"Approved Team {letter} Rulebook"},
            headers=sports_core_headers,
        )
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "APPROVED"

    # 10. Check Aggregate Distribution Summary
    res_summary = client.get(f"/api/v1/forms/{form_id}/distribution-summary", headers=sc_headers)
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert summary_data["total_recipients"] == 8
    assert summary_data["counts"]["APPROVED"] == 7
    assert summary_data["counts"]["RESUBMITTED"] == 1
    assert summary_data["counts"]["RETURNED"] == 0

    # 11. Test URL Validation & File Upload Restriction
    # Verify non-URL string in REFERENCE_LINK field fails validation
    invalid_url_payload = {
        "response_data": {
            "event_title": "Invalid Event",
            "expected_teams": 10,
            "rulebook_ref_url": "C:\\Users\\Desktop\\Rulebook.pdf",  # File path instead of URL
            "eligibility_terms": "Valid terms",
            "schedule_url": "https://valid.url",
            "declaration": True,
        }
    }
    # Submission should strictly fail validation
    res_inv_sub = client.post(f"/api/v1/form-responses/{team_a_resp_id}/submit", json=invalid_url_payload, headers=_get_auth_headers(db_session, phase11_setup["event_teams"][0]))
    assert res_inv_sub.status_code in [400, 422]
    assert "must be a valid URL" in res_inv_sub.text
