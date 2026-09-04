#!/usr/bin/env python3
"""
Production Database Purge & Fresh Initialization Utility
Paradox Sports Operations Management System (OMS)

Completely wipes all operational and transactional data across all database tables:
- Zero users (all user accounts, profiles, sessions, role assignments, and verticals removed)
- Zero verticals
- Zero organizations
- Zero tasks, issues, meetings, requirements, and work reports
- Zero forms, submissions, responses, and workflow history
- Zero events, event team profiles, and readiness items
- Zero calendar entries, announcements, directives, and notifications
- Zero audit logs and communication logs

PRESERVES:
- All table schemas, constraints, foreign keys, indexes, and types (Zero DDL changes)
- Alembic migration history (alembic_version preserved so migration state remains at head)
- Canonical RBAC Roles (7 standard roles) & Core Permissions (84 permissions)
- Canonical System Configuration Parameters (10 standard operational thresholds)

The resulting database is in a completely clean, pristine, initial state
ready for fresh production setup.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import inspect, text, select
from app.core.database import SessionLocal, engine
from app.models.governance import SystemConfig, ConfigValueType
from app.services.rbac_service import ensure_canonical_roles_and_permissions

# Canonical System Configurations
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

# Standard dependency-ordered table list for fallback DELETE execution
REVERSE_DEPENDENCY_TABLES = [
    "system_test_records",
    "notifications",
    "directive_acknowledgements",
    "directives",
    "communication_logs",
    "ownership_transfers",
    "daily_report_tasks",
    "daily_report_history",
    "daily_work_reports",
    "weekly_reports",
    "issue_comments",
    "issue_assignees",
    "issue_history",
    "issues",
    "task_comments",
    "task_history",
    "tasks",
    "meeting_action_items",
    "meeting_participants",
    "meetings",
    "requirement_messages",
    "requirements",
    "form_checklist_items",
    "form_workflow_history",
    "form_responses",
    "form_submissions",
    "form_distributions",
    "form_versions",
    "forms",
    "event_readiness_items",
    "event_members",
    "event_team_profiles",
    "events",
    "calendar_entry_users",
    "calendar_entries",
    "announcements",
    "form_reviewers",
    "user_permission_overrides",
    "audit_logs",
    "user_sessions",
    "user_roles",
    "user_verticals",
    "user_profiles",
    "users",
    "verticals",
    "organizations",
    "faqs",
    "system_configs",
    "role_permissions",
    "permissions",
    "roles",
]


def wipe_entire_database(confirmed: bool = False) -> bool:
    print("\n" + "=" * 80)
    print("PARADOX SPORTS OMS — COMPLETE DATABASE DATA PURGE")
    print("=" * 80)
    print("WARNING: This operation will permanently wipe ALL operational records:")
    print("  - ALL Users (including Administrator accounts)")
    print("  - ALL Verticals and Organizations")
    print("  - ALL Tasks, Meetings, Events, Issues, Forms, and Reports")
    print("  - ALL Audit logs, Notifications, and Session tokens")
    print("  - Schema, tables, and Alembic migration state will remain 100% intact.")
    print("=" * 80 + "\n")

    if not confirmed:
        try:
            choice = input("Are you absolutely sure you want to wipe all data? (yes/no): ").strip().lower()
        except EOFError:
            choice = "no"
        if choice not in ("yes", "y"):
            print("[-] Operation aborted. No data was modified.")
            return False

    db = SessionLocal()
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # Collect all tables except alembic_version
        tables_to_wipe = [t for t in existing_tables if t != "alembic_version"]

        print(f"[*] Identified {len(tables_to_wipe)} operational tables in PostgreSQL.")
        print("[*] Executing cascading purge...")

        # Fast atomic wipe: TRUNCATE TABLE ... RESTART IDENTITY CASCADE
        try:
            table_list_sql = ", ".join(f'"{t}"' for t in tables_to_wipe)
            db.execute(text(f"TRUNCATE TABLE {table_list_sql} RESTART IDENTITY CASCADE;"))
            db.commit()
            print("  [+] Cascading truncate completed successfully across all tables.")
        except Exception as truncate_err:
            db.rollback()
            print(f"  [!] Notice: Cascading truncate note ({truncate_err}). Falling back to dependency delete...")
            # Fallback to ordered DELETE
            for tbl in REVERSE_DEPENDENCY_TABLES:
                if tbl in existing_tables:
                    try:
                        res = db.execute(text(f'DELETE FROM "{tbl}";'))
                        if res.rowcount > 0:
                            print(f"  [-] {tbl}: cleared {res.rowcount:,} records")
                    except Exception as e:
                        print(f"  [!] {tbl}: skipped ({e})")
            db.commit()

        # Re-initialize clean system metadata
        print("\n[*] Initializing clean RBAC baseline and canonical parameters...")
        ensure_canonical_roles_and_permissions(db)

        # Seed canonical configuration parameters
        for key, val, vtype, desc in CANONICAL_CONFIGS:
            db.add(
                SystemConfig(
                    key=key,
                    value=val,
                    value_type=vtype,
                    description=desc,
                    is_active=True,
                    updated_by_id=None,
                )
            )
        db.commit()
        print("  [+] Canonical RBAC roles and core permissions initialized.")
        print("  [+] Standard system governance parameters initialized.")

        # Post-wipe verification
        print("\n" + "=" * 80)
        print("DATABASE PURGE VERIFICATION REPORT:")
        print("=" * 80)
        verify_tables = [
            ("users", "User Accounts"),
            ("verticals", "Vertical Divisions"),
            ("organizations", "Organizations"),
            ("tasks", "Tasks"),
            ("meetings", "Meetings"),
            ("events", "Events"),
            ("issues", "Issues & Incidents"),
            ("forms", "Forms"),
            ("audit_logs", "Audit Trail"),
            ("notifications", "Notifications"),
            ("roles", "Canonical RBAC Roles"),
            ("permissions", "RBAC Permissions"),
            ("system_configs", "Canonical System Configs"),
        ]

        for tbl, label in verify_tables:
            if tbl in existing_tables:
                cnt = db.execute(text(f'SELECT count(*) FROM "{tbl}"')).scalar()
                print(f"  - {label:<28}: {cnt:>5} records")

        print("=" * 80)
        print("\n[SUCCESS] The database is now completely clean and pristine!")
        print("All tables exist with zero operational data.\n")
        print("Next step: Provision your initial System Administrator account:")
        print("  python scripts/create_production_admin.py\n")
        return True

    except Exception as exc:
        db.rollback()
        print(f"\n[FATAL ERROR] Data wipe failed: {exc}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Wipe all operational data from the database while preserving table schemas and RBAC foundation."
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Execute wipe without interactive confirmation prompt.",
    )
    args = parser.parse_args()
    success = wipe_entire_database(confirmed=args.yes)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
