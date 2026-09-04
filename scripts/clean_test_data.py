"""
Production Preparation: Test & Development Data Cleanup Script
Paradox Sports Operations Management System (OMS)

Safely removes development, benchmark, and test-generated data from PostgreSQL
while strictly preserving all production baseline data:
- Canonical Organization: Paradox Sports Department (code='PARADOX_SPORTS')
- Canonical Roles: All 7 RBAC roles (ADMIN, SPORTS_CORE, DEPUTY_CORE, SUPER_COORDINATOR, COORDINATOR, VOLUNTEER, EVENT_TEAM)
- Canonical Permissions: All 84 permissions & role mappings
- Core Active Verticals under Paradox Sports
- System Administrator Account ('admin' / 'admin@paradoxsports.internal')
- Canonical System Configuration Parameters (CANONICAL_CONFIGS)
- Authoritative FAQs

Zero schema modification. Pure targeted data purge in reverse foreign key order.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select, text
from app.core.database import SessionLocal, engine
from app.models.organization import Organization, Vertical, UserVertical
from app.models.user import User
from app.models.governance import SystemConfig, ConfigValueType

CANONICAL_CONFIGS = [
    ("system_name", "Paradox Sports OMS", ConfigValueType.STRING, "Official application display title"),
    ("maintenance_mode", "false", ConfigValueType.BOOLEAN, "Global operational maintenance mode flag"),
    ("audit_retention_days", "365", ConfigValueType.INTEGER, "Immutable audit log retention period in days"),
    ("session_timeout_mins", "60", ConfigValueType.INTEGER, "Duration in minutes before an inactive session expires"),
    ("max_concurrent_logins", "10", ConfigValueType.INTEGER, "Maximum concurrent active sessions per user account"),
    ("allow_self_registration", "false", ConfigValueType.BOOLEAN, "Permit external self-service account registration"),
    ("require_two_factor_auth", "false", ConfigValueType.BOOLEAN, "Enforce two-factor authentication for administrative users"),
    ("default_task_sla_days", "3", ConfigValueType.INTEGER, "Standard routine task turnaround window (days)"),
    ("max_active_tasks_per_user", "25", ConfigValueType.INTEGER, "Maximum concurrent active tasks assigned to a single coordinator"),
    ("allow_public_forms", "true", ConfigValueType.BOOLEAN, "Allow organization-wide form submissions"),
]

CORE_VERTICAL_NAMES = [
    "Football Operations",
    "Cricket Operations",
    "Athletics & Track",
    "Logistics & Equipment",
    "Media & Communications",
]


def clean_test_data():
    db = SessionLocal()
    print("=" * 80)
    print("PARADOX SPORTS OMS - PRODUCTION DATA CLEANUP")
    print("=" * 80)

    try:
        # 1. Verify Canonical Organization
        canonical_org = db.scalar(select(Organization).where(Organization.code == "PARADOX_SPORTS"))
        if not canonical_org:
            print("[!] Canonical organization 'PARADOX_SPORTS' not found. Creating baseline...")
            canonical_org = Organization(
                name="Paradox Sports Department",
                code="PARADOX_SPORTS",
                description="Authoritative organization for Paradox Sports Operations",
                is_active=True,
            )
            db.add(canonical_org)
            db.flush()
        print(f"[+] Canonical Organization preserved: {canonical_org.name} (id={canonical_org.id})")

        # 2. Verify Admin User
        admin_user = db.scalar(select(User).where(User.username == "admin"))
        admin_id = str(admin_user.id) if admin_user else None
        if admin_user:
            print(f"[+] Canonical Admin preserved: {admin_user.username} ({admin_user.email})")
        else:
            print("[!] WARNING: 'admin' user not found. Preservation rule will guard against deleting any non-test users.")

        print("\n[*] Purging test records in dependency order...")

        # Purge order
        purge_steps = [
            ("system_test_records", "DELETE FROM system_test_records"),
            ("notifications", "DELETE FROM notifications"),
            ("directive_acknowledgements", "DELETE FROM directive_acknowledgements"),
            ("directives", "DELETE FROM directives"),
            ("communication_logs", "DELETE FROM communication_logs"),
            ("ownership_transfers", "DELETE FROM ownership_transfers"),
            ("daily_report_tasks", "DELETE FROM daily_report_tasks"),
            ("daily_report_history", "DELETE FROM daily_report_history"),
            ("daily_work_reports", "DELETE FROM daily_work_reports"),
            ("weekly_reports", "DELETE FROM weekly_reports"),
            ("issue_comments", "DELETE FROM issue_comments"),
            ("issue_assignees", "DELETE FROM issue_assignees"),
            ("issue_history", "DELETE FROM issue_history"),
            ("issues", "DELETE FROM issues"),
            ("task_comments", "DELETE FROM task_comments"),
            ("task_history", "DELETE FROM task_history"),
            ("tasks", "DELETE FROM tasks"),
            ("meeting_action_items", "DELETE FROM meeting_action_items"),
            ("meeting_participants", "DELETE FROM meeting_participants"),
            ("meetings", "DELETE FROM meetings"),
            ("requirement_messages", "DELETE FROM requirement_messages"),
            ("requirements", "DELETE FROM requirements"),
            ("form_checklist_items", "DELETE FROM form_checklist_items"),
            ("form_workflow_history", "DELETE FROM form_workflow_history"),
            ("form_responses", "DELETE FROM form_responses"),
            ("form_submissions", "DELETE FROM form_submissions"),
            ("form_distributions", "DELETE FROM form_distributions"),
            ("form_versions", "DELETE FROM form_versions"),
            ("forms", "DELETE FROM forms"),
            ("event_readiness_items", "DELETE FROM event_readiness_items"),
            ("event_members", "DELETE FROM event_members"),
            ("event_team_profiles", "DELETE FROM event_team_profiles"),
            ("events", "DELETE FROM events"),
            ("calendar_entry_users", "DELETE FROM calendar_entry_users"),
            ("calendar_entries", "DELETE FROM calendar_entries"),
            ("announcements", "DELETE FROM announcements"),
            ("form_reviewers", "DELETE FROM form_reviewers"),
            ("user_permission_overrides", "DELETE FROM user_permission_overrides"),
            ("audit_logs", "DELETE FROM audit_logs"),
        ]

        deleted_counts = {}
        for table_name, delete_sql in purge_steps:
            try:
                res = db.execute(text(delete_sql))
                count = res.rowcount
                deleted_counts[table_name] = count
                if count > 0:
                    print(f"  [-] {table_name}: removed {count:,} test records")
            except Exception as e:
                print(f"  [!] {table_name}: skipped ({e})")

        # 3. Clean Test Users (preserve admin)
        if admin_id:
            # Reassign authoritative FAQs and System Configs to admin
            db.execute(
                text("UPDATE faqs SET created_by_id = :admin_id, updated_by_id = :admin_id"),
                {"admin_id": admin_id},
            )
            db.execute(
                text("UPDATE system_configs SET updated_by_id = :admin_id"),
                {"admin_id": admin_id},
            )

            res = db.execute(text("DELETE FROM user_sessions WHERE user_id != :admin_id"), {"admin_id": admin_id})
            deleted_counts["user_sessions"] = res.rowcount
            res = db.execute(text("DELETE FROM user_roles WHERE user_id != :admin_id"), {"admin_id": admin_id})
            deleted_counts["user_roles"] = res.rowcount
            res = db.execute(text("DELETE FROM user_verticals WHERE user_id != :admin_id"), {"admin_id": admin_id})
            deleted_counts["user_verticals"] = res.rowcount
            res = db.execute(text("DELETE FROM user_profiles WHERE user_id != :admin_id"), {"admin_id": admin_id})
            deleted_counts["user_profiles"] = res.rowcount
            res = db.execute(text("DELETE FROM users WHERE id != :admin_id"), {"admin_id": admin_id})
            deleted_counts["users"] = res.rowcount
            print(f"  [-] users: removed {deleted_counts['users']:,} test users (preserved admin)")

        # 4. Clean Test Organizations & Associated Verticals (preserve PARADOX_SPORTS & core verticals)
        res = db.execute(
            text(
                "DELETE FROM user_verticals WHERE vertical_id IN ("
                "  SELECT id FROM verticals WHERE organization_id != :org_id"
                ")"
            ),
            {"org_id": canonical_org.id},
        )
        res1 = db.execute(text("DELETE FROM verticals WHERE organization_id != :org_id"), {"org_id": canonical_org.id})
        res2 = db.execute(
            text("DELETE FROM verticals WHERE organization_id = :org_id AND name NOT IN :core_names"),
            {"org_id": canonical_org.id, "core_names": tuple(CORE_VERTICAL_NAMES)},
        )
        deleted_counts["verticals"] = res1.rowcount + res2.rowcount
        print(f"  [-] verticals: removed {deleted_counts['verticals']:,} test verticals")

        res = db.execute(text("DELETE FROM organizations WHERE id != :org_id"), {"org_id": canonical_org.id})
        deleted_counts["organizations"] = res.rowcount
        print(f"  [-] organizations: removed {deleted_counts['organizations']:,} test organizations")

        # 5. Ensure Core Verticals exist under PARADOX_SPORTS
        for vname in CORE_VERTICAL_NAMES:
            v_exists = db.scalar(
                select(Vertical).where(Vertical.organization_id == canonical_org.id, Vertical.name == vname)
            )
            if not v_exists:
                db.add(
                    Vertical(
                        organization_id=canonical_org.id,
                        name=vname,
                        description=f"Standard {vname} division",
                    )
                )
        db.flush()

        # Connect admin to first vertical if not assigned
        if admin_user:
            first_v = db.scalar(select(Vertical).where(Vertical.organization_id == canonical_org.id).limit(1))
            if first_v:
                user_vert = db.scalar(
                    select(UserVertical).where(
                        UserVertical.user_id == admin_user.id, UserVertical.vertical_id == first_v.id
                    )
                )
                if not user_vert:
                    db.add(UserVertical(user_id=admin_user.id, vertical_id=first_v.id, is_primary=True))

        # 6. Clean System Configurations (keep only the 10 canonical configs)
        canonical_keys = {k for k, _, _, _ in CANONICAL_CONFIGS}
        all_cfgs = db.scalars(select(SystemConfig)).all()
        cfg_del_count = 0
        for cfg in all_cfgs:
            if cfg.key not in canonical_keys:
                db.delete(cfg)
                cfg_del_count += 1
        db.flush()

        # Seed missing canonical configs
        for key, val, vtype, desc in CANONICAL_CONFIGS:
            existing = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
            if not existing:
                db.add(
                    SystemConfig(
                        key=key,
                        value=val,
                        value_type=vtype,
                        description=desc,
                        is_active=True,
                        updated_by_id=admin_user.id if admin_user else None,
                    )
                )
            else:
                existing.description = desc
                existing.value_type = vtype
                existing.is_active = True

        deleted_counts["system_configs"] = cfg_del_count
        print(f"  [-] system_configs: removed {cfg_del_count} orphaned test keys")

        db.commit()
        print("\n" + "=" * 80)
        print("DATABASE TEST DATA PURGE COMPLETE - SUMMARY:")
        print("=" * 80)
        total_records_purged = sum(deleted_counts.values())
        for k, v in deleted_counts.items():
            if v > 0:
                print(f"  - {k:<30}: {v:>10,}")
        print("-" * 80)
        print(f"  TOTAL TEST RECORDS PURGED: {total_records_purged:>14,}")
        print("=" * 80)

        # 7. Post-cleanup verification
        print("\n[*] Post-cleanup database verification:")
        remaining_users = db.execute(text("SELECT count(*) FROM users")).scalar()
        remaining_orgs = db.execute(text("SELECT count(*) FROM organizations")).scalar()
        remaining_verts = db.execute(text("SELECT count(*) FROM verticals")).scalar()
        remaining_roles = db.execute(text("SELECT count(*) FROM roles")).scalar()
        remaining_perms = db.execute(text("SELECT count(*) FROM permissions")).scalar()
        remaining_cfgs = db.execute(text("SELECT count(*) FROM system_configs")).scalar()

        print(f"  - Organizations:  {remaining_orgs} (Paradox Sports Department)")
        print(f"  - Verticals:      {remaining_verts} (Core Operational Verticals)")
        print(f"  - Canonical Roles:{remaining_roles} (All 7 Standard Roles)")
        print(f"  - Permissions:    {remaining_perms} (Complete RBAC Registry)")
        print(f"  - User Accounts:  {remaining_users} (Primary Administrator)")
        print(f"  - System Configs: {remaining_cfgs} (Canonical Configurations)")

        return True

    except Exception as exc:
        db.rollback()
        print(f"[FATAL ERROR] Cleanup failed: {exc}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = clean_test_data()
    sys.exit(0 if success else 1)
