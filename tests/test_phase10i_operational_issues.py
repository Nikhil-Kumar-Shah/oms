"""
Phase 10I: Operational Issue Form + Universal Selector Integration Test Suite

Tests:
1. Issue creation with Universal Selector audience scope.
2. Composite multi-assignee resolution (Vertical + Role Groups + Individual Users).
3. Database persistence of issue_assignees junction table.
4. Cross-vertical permission enforcement (Non-executives barred with 403 Forbidden).
5. Elimination of 422 errors via automatic coercion of empty optional string fields to null.
6. Universal Selector user search matching by Username, Full Name, and Email.
7. Multi-assignee authorization access verification.
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import generate_session_token, hash_session_token
from app.models.issue import Issue, IssueAssignee, IssueSensitivity, IssueStatus
from app.models.organization import Organization, UserVertical, Vertical, VerticalStatus
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.session import UserSession
from app.models.user import AccountStatus, User

_phase10i_sessions = {}


def _auth_headers(user: User) -> dict:
    tok = _phase10i_sessions.get(user.id)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def i_env(db_session: Session):
    """Sets up an isolated test environment with distinct verticals, roles, and users."""
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(name="Paradox Sports Org 10I", code="PARADOX10I")
        db_session.add(org)
        db_session.flush()

    uid = uuid.uuid4().hex[:6]

    v_football = Vertical(
        organization_id=org.id,
        name=f"Football 10I {uid}",
        description="Football Operations",
        status=VerticalStatus.ACTIVE,
    )
    v_cricket = Vertical(
        organization_id=org.id,
        name=f"Cricket 10I {uid}",
        description="Cricket Operations",
        status=VerticalStatus.ACTIVE,
    )
    db_session.add_all([v_football, v_cricket])
    db_session.flush()

    # Ensure issues.create permission exists
    perm_create = db_session.query(Permission).filter(Permission.code == "issues.create").first()
    if not perm_create:
        perm_create = Permission(code="issues.create", description="Create Issues", category="issues")
        db_session.add(perm_create)
        db_session.flush()

    def _create_user(uname: str, rname: str, vert: Vertical = None, full_name: str = None, email: str = None) -> User:
        u = User(
            email=email or f"{uname}_{uid}@paradox.test",
            username=f"{uname}_{uid}",
            password_hash="fakehash",
            full_name=full_name or f"{uname.title()} Fullname",
            account_status=AccountStatus.ACTIVE,
        )
        db_session.add(u)
        db_session.flush()

        role = db_session.query(Role).filter(Role.name == rname).first()
        if not role:
            role = Role(name=rname, description=f"{rname} Role")
            db_session.add(role)
            db_session.flush()

        # Grant issues.create to role
        rp = db_session.query(RolePermission).filter(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == perm_create.id,
        ).first()
        if not rp:
            db_session.add(RolePermission(role_id=role.id, permission_id=perm_create.id))

        db_session.add(UserRole(user_id=u.id, role_id=role.id))

        if vert:
            db_session.add(UserVertical(user_id=u.id, vertical_id=vert.id))
        db_session.flush()

        tok = generate_session_token()
        _phase10i_sessions[u.id] = tok
        sess = UserSession(
            user_id=u.id,
            session_token_hash=hash_session_token(tok),
            ip_address="127.0.0.1",
            user_agent="pytest-10i",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        db_session.add(sess)
        db_session.flush()
        return u

    admin = _create_user("admin10i", "ADMIN", v_football)
    core = _create_user("core10i", "SPORTS_CORE", v_football)
    coord_football = _create_user("coord_fb_10i", "COORDINATOR", v_football, full_name="Carlos Coordinator", email=f"carlos.coord_{uid}@paradox.test")
    coord_cricket = _create_user("coord_ck_10i", "COORDINATOR", v_cricket, full_name="Chris Cricket", email=f"chris.cricket_{uid}@paradox.test")
    vol_a = _create_user("vola_10i", "VOLUNTEER", v_football, full_name="Alice Volunteer", email=f"alice.vola_{uid}@paradox.test")
    vol_b = _create_user("volb_10i", "VOLUNTEER", v_football, full_name=f"Bob Searchtarget {uid}", email=f"target.search_{uid}@paradox.test")

    db_session.commit()

    return {
        "admin": admin,
        "core": core,
        "coord_football": coord_football,
        "coord_cricket": coord_cricket,
        "vol_a": vol_a,
        "vol_b": vol_b,
        "v_football": v_football,
        "v_cricket": v_cricket,
    }


def test_create_issue_with_universal_selector_audience(client: TestClient, i_env, db_session: Session):
    """Verifies that an issue can be created using Universal Selector vertical_ids."""
    headers = _auth_headers(i_env["coord_football"])
    payload = {
        "title": "Shortage of Football referee kits",
        "description": "Group B referee kits are missing for the upcoming tournament.",
        "vertical_ids": [str(i_env["v_football"].id)],
        "sensitivity": "NORMAL",
        "action_required": "Provide 4 referee shirts and whistles.",
    }

    res = client.post("/api/v1/issues", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["title"] == "Shortage of Football referee kits"
    assert data["vertical_id"] == str(i_env["v_football"].id)
    assert data["vertical_name"] == i_env["v_football"].name
    assert data["raised_by_id"] == str(i_env["coord_football"].id)


def test_create_issue_with_composite_assignees(client: TestClient, i_env, db_session: Session):
    """
    Verifies composite multi-assignee assignment:
    Vertical + Role Group (e.g. COORDINATOR) + Individual Users.
    Verifies all resolved users are stored in issue_assignees junction table.
    """
    headers = _auth_headers(i_env["admin"])
    payload = {
        "title": "Coordinate Multi-Sport Ground Maintenance",
        "description": "Ground lines must be repainted for football and volunteers mobilized.",
        "vertical_ids": [str(i_env["v_football"].id)],
        "assignee_role_ids": ["COORDINATOR"],
        "assignee_user_ids": [str(i_env["vol_a"].id)],
        "sensitivity": "NORMAL",
        "action_required": "Confirm readiness by Friday evening.",
    }

    res = client.post("/api/v1/issues", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    issue_id = data["id"]

    # Check response assignees
    assert "assignees" in data
    assert "assignee_ids" in data
    assignee_ids = data["assignee_ids"]

    # Both coordinators and vol_a should be resolved in assignees
    assert str(i_env["vol_a"].id) in assignee_ids
    assert str(i_env["coord_football"].id) in assignee_ids

    # Query database issue_assignees junction table directly
    stored_assignees = db_session.query(IssueAssignee).filter(IssueAssignee.issue_id == issue_id).all()
    stored_uids = {str(ia.user_id) for ia in stored_assignees}
    assert str(i_env["vol_a"].id) in stored_uids
    assert str(i_env["coord_football"].id) in stored_uids


def test_cross_vertical_issue_creation_rejected(client: TestClient, i_env, db_session: Session):
    """Verifies that non-executives cannot raise issues for verticals they do not belong to."""
    headers = _auth_headers(i_env["coord_football"])
    # Football coordinator attempting to raise issue for Cricket vertical
    payload = {
        "title": "Unauthorized cross-vertical issue",
        "description": "Trying to raise an issue in cricket division.",
        "vertical_ids": [str(i_env["v_cricket"].id)],
        "sensitivity": "NORMAL",
    }

    res = client.post("/api/v1/issues", json=payload, headers=headers)
    assert res.status_code == 403, res.text
    assert "Cross-vertical violation" in res.json()["error"]["message"]


def test_empty_optional_fields_coercion(client: TestClient, i_env, db_session: Session):
    """
    Verifies that empty string values for optional fields:
    deadline="", action_required="", remarks="", assigned_to_id=""
    do NOT trigger 422 Unprocessable Content errors.
    """
    headers = _auth_headers(i_env["coord_football"])
    payload = {
        "title": "Clean empty fields validation test",
        "description": "Testing empty string coercion for optional fields.",
        "vertical_id": str(i_env["v_football"].id),
        "assigned_to_id": "",
        "action_required": "",
        "deadline": "",
        "evidence_link": "",
        "remarks": "",
        "event_reference": "",
    }

    res = client.post("/api/v1/issues", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["deadline"] is None
    assert data["action_required"] is None
    assert data["evidence_link"] is None
    assert data["assigned_to_id"] is None


def test_search_users_by_username_fullname_email(client: TestClient, i_env, db_session: Session):
    """
    Verifies that the Universal Selector search endpoint matches users by:
    1. Username
    2. Full Name
    3. Email
    """
    headers = _auth_headers(i_env["admin"])

    # 1. Match by username
    res_un = client.get(
        f"/api/v1/organization/selector-options?selection_type=USER&search={i_env['coord_football'].username}",
        headers=headers,
    )
    assert res_un.status_code == 200
    items_un = res_un.json()["items"]
    assert any(it["id"] == str(i_env["coord_football"].id) for it in items_un)

    # 2. Match by full name
    res_fn = client.get(
        "/api/v1/organization/selector-options?selection_type=USER&search=Searchtarget",
        headers=headers,
    )
    assert res_fn.status_code == 200
    items_fn = res_fn.json()["items"]
    assert any(it["id"] == str(i_env["vol_b"].id) for it in items_fn)

    # 3. Match by email
    res_em = client.get(
        f"/api/v1/organization/selector-options?selection_type=USER&search={i_env['vol_b'].email}",
        headers=headers,
    )
    assert res_em.status_code == 200
    items_em = res_em.json()["items"]
    assert any(it["id"] == str(i_env["vol_b"].id) for it in items_em)


def test_multi_assignee_authorization_access(client: TestClient, i_env, db_session: Session):
    """
    Verifies that a user who is assigned as part of a multi-assignee group
    has authorization to view the issue details via GET /api/v1/issues/{id}.
    """
    # Create issue with Vol A as one of multiple assignees
    headers_admin = _auth_headers(i_env["admin"])
    payload = {
        "title": "Confidential Security Audit for Multi-Assignees",
        "description": "Sensitive security review requiring volunteer assistance.",
        "vertical_ids": [str(i_env["v_football"].id)],
        "assignee_user_ids": [str(i_env["vol_a"].id)],
        "sensitivity": "CONFIDENTIAL",
    }
    res = client.post("/api/v1/issues", json=payload, headers=headers_admin)
    assert res.status_code == 201, res.text
    issue_id = res.json()["id"]

    # Vol A should be able to view this confidential issue because they are assigned to it
    headers_vola = _auth_headers(i_env["vol_a"])
    res_get = client.get(f"/api/v1/issues/{issue_id}", headers=headers_vola)
    assert res_get.status_code == 200, res_get.text
    assert res_get.json()["id"] == issue_id

    # Vol B (not assigned) should be denied with 403 Forbidden
    headers_volb = _auth_headers(i_env["vol_b"])
    res_denied = client.get(f"/api/v1/issues/{issue_id}", headers=headers_volb)
    assert res_denied.status_code == 403, res_denied.text
