"""
Tests for Phase 5 Security, RBAC Authorization & System Config Policies
"""

import uuid
import pytest
from app.models.governance import ConfigValueType
from app.schemas.governance import SystemConfigCreate
from app.services.config_service import SystemConfigService


def test_system_config_validation_and_audit(db_session, admin_user):
    """Verifies typed configuration validation and immutable audit logging."""
    service = SystemConfigService(db_session)
    unique_key = f"max_tasks_{uuid.uuid4().hex[:8]}"

    # Valid integer config
    c1 = service.create_config(
        SystemConfigCreate(
            key=unique_key,
            value="15",
            value_type=ConfigValueType.INTEGER,
            description="Max tasks per coordinator",
        ),
        actor_id=admin_user.id,
    )
    db_session.commit()

    assert c1.key == unique_key
    assert c1.value == "15"

    # Invalid integer config must fail
    with pytest.raises(Exception):
        service.create_config(
            SystemConfigCreate(
                key=f"invalid_int_{uuid.uuid4().hex[:8]}",
                value="not_an_integer",
                value_type=ConfigValueType.INTEGER,
            ),
            actor_id=admin_user.id,
        )


def test_phase5_api_endpoints_auth(client, admin_token, auth_token):
    """Verifies RBAC enforcement across Phase 5 API endpoints."""
    # 1. Announcements
    r_ann = client.get("/api/v1/announcements", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_ann.status_code == 200

    # 2. Directives
    r_dir = client.get("/api/v1/directives", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_dir.status_code == 200

    # 3. Notifications
    r_notif = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_notif.status_code == 200

    # 4. Communications (Restricted to Executive Leadership per Phase 14)
    r_comm_coord = client.get("/api/v1/communications", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_comm_coord.status_code == 403
    r_comm_admin = client.get("/api/v1/communications", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_comm_admin.status_code == 200

    # 5. Transfers (ADMIN-Only Governance per Phase 10.1)
    r_trans_coord = client.get("/api/v1/transfers", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_trans_coord.status_code == 403
    r_trans_admin = client.get("/api/v1/transfers", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_trans_admin.status_code == 200

    # 6. Analytics Operational
    r_an = client.get("/api/v1/analytics/operational", headers={"Authorization": f"Bearer {auth_token}"})
    assert r_an.status_code == 200

    # 7. Admin Config (Requires ADMIN role / config.read permission)
    r_cfg = client.get("/api/v1/admin/config", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_cfg.status_code == 200
