#!/usr/bin/env python3
"""
Server & Production Readiness Health Check Utility
Paradox Sports Operations Management System (OMS)

Usage:
    python scripts/check_server.py
    python scripts/check_server.py --url http://127.0.0.1:8000
    python scripts/check_server.py --skip-http

Validates:
1. Environment & Security Configuration (APP_ENV, DEBUG, SECRET_KEY, CORS)
2. PostgreSQL Database Connectivity, Latency, and Version
3. Alembic Database Migration Status
4. Core Entity Integrity (Users, Roles, Permissions, Verticals)
5. Live HTTP Service Health Probes (/health, /)
"""

import argparse
import os
import sys
import time
from urllib.parse import urlparse

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from app.core.config import get_settings
from app.core.database import engine, verify_database_connection
from app.models.user import User, AccountStatus
from app.models.rbac import Role, Permission
from app.models.organization import Vertical
from app.models.governance import SystemConfig


# ANSI Color Codes for terminal formatting
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_configuration(settings) -> tuple[bool, list[str]]:
    messages = []
    has_critical_failure = False

    messages.append(f"  • Environment:       {CYAN}{settings.APP_ENV}{RESET}")
    messages.append(f"  • Debug Mode:        {YELLOW if settings.DEBUG else GREEN}{settings.DEBUG}{RESET}")
    messages.append(f"  • Server Bind:       {settings.HOST}:{settings.PORT}")

    # Production checks
    if settings.is_production:
        if settings.DEBUG:
            messages.append(f"    [{RED}FAIL{RESET}] DEBUG is enabled in production! Must be False.")
            has_critical_failure = True
        else:
            messages.append(f"    [{GREEN}PASS{RESET}] DEBUG is disabled for production.")

        if "change-me" in settings.SECRET_KEY.lower() or "dev-secret" in settings.SECRET_KEY.lower() or len(settings.SECRET_KEY) < 32:
            messages.append(f"    [{RED}FAIL{RESET}] Insecure SECRET_KEY in production mode.")
            has_critical_failure = True
        else:
            messages.append(f"    [{GREEN}PASS{RESET}] SECRET_KEY meets cryptographic complexity requirements.")
    else:
        messages.append(f"    [{GREEN}PASS{RESET}] Development configuration active.")

    # Database URL masking
    parsed_db = urlparse(settings.DATABASE_URL.replace("+psycopg2", ""))
    safe_db_host = parsed_db.hostname or "unknown"
    safe_db_name = parsed_db.path.lstrip("/") or "unknown"
    is_azure = "postgres.database.azure.com" in safe_db_host
    messages.append(f"  • Target Database:   {safe_db_host}:{parsed_db.port or 5432}/{safe_db_name} (Azure: {is_azure})")

    return not has_critical_failure, messages


def check_database() -> tuple[bool, list[str]]:
    messages = []
    try:
        health_info = verify_database_connection()
        latency = health_info.get("latency_ms", 0.0)
        version = " ".join(health_info.get("server_version", []))
        messages.append(f"  [{GREEN}PASS{RESET}] PostgreSQL reachable (Latency: {latency}ms)")
        messages.append(f"  • Server Version:    {version}")
        return True, messages
    except Exception as exc:
        messages.append(f"  [{RED}FAIL{RESET}] PostgreSQL connection failed: {exc}")
        return False, messages


def check_migrations() -> tuple[bool, list[str]]:
    messages = []
    try:
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        messages.append(f"  • Expected Head:     {head_rev}")
        messages.append(f"  • Current Database:  {current_rev}")

        if current_rev == head_rev:
            messages.append(f"  [{GREEN}PASS{RESET}] Database schema is fully synchronized to latest migration.")
            return True, messages
        else:
            messages.append(f"  [{YELLOW}WARN{RESET}] Database schema does not match head revision ({current_rev} != {head_rev}). Run 'alembic upgrade head'.")
            return False, messages
    except Exception as exc:
        messages.append(f"  [{RED}FAIL{RESET}] Unable to check migration status: {exc}")
        return False, messages


def check_entities() -> tuple[bool, list[str]]:
    messages = []
    try:
        with engine.connect() as conn:
            user_count = conn.execute(text("SELECT count(*) FROM users;")).scalar()
            admin_count = conn.execute(text(
                "SELECT count(*) FROM users u "
                "JOIN user_roles ur ON u.id = ur.user_id "
                "JOIN roles r ON ur.role_id = r.id "
                "WHERE r.name = 'ADMIN' AND u.account_status = 'ACTIVE';"
            )).scalar()
            vertical_count = conn.execute(text("SELECT count(*) FROM verticals;")).scalar()
            role_count = conn.execute(text("SELECT count(*) FROM roles;")).scalar()
            perm_count = conn.execute(text("SELECT count(*) FROM permissions;")).scalar()
            config_count = conn.execute(text("SELECT count(*) FROM system_configs;")).scalar()

        messages.append(f"  • Total Users:       {user_count} (Active Admins: {admin_count})")
        messages.append(f"  • Verticals:         {vertical_count}")
        messages.append(f"  • RBAC Roles:        {role_count} roles, {perm_count} permissions")
        messages.append(f"  • System Configs:    {config_count} operational keys")

        if admin_count == 0:
            messages.append(f"  [{YELLOW}WARN{RESET}] No active ADMIN user found. Run 'python scripts/create_production_admin.py' to provision one.")
        else:
            messages.append(f"  [{GREEN}PASS{RESET}] Administrator account provisioned and active.")

        return True, messages
    except Exception as exc:
        messages.append(f"  [{RED}FAIL{RESET}] Error querying entity integrity: {exc}")
        return False, messages


def check_http_endpoints(base_url: str) -> tuple[bool, list[str]]:
    messages = []
    try:
        import urllib.request
        import json

        health_url = f"{base_url.rstrip('/')}/health"
        root_url = f"{base_url.rstrip('/')}/"

        # Check /health
        start = time.perf_counter()
        req = urllib.request.Request(health_url, headers={"User-Agent": "OMS-HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            elapsed = (time.perf_counter() - start) * 1000
            status_code = resp.status
            body = json.loads(resp.read().decode())
            if status_code == 200 and body.get("status") == "healthy":
                messages.append(f"  [{GREEN}PASS{RESET}] GET {health_url} -> 200 OK ({elapsed:.1f}ms)")
            else:
                messages.append(f"  [{YELLOW}WARN{RESET}] GET {health_url} returned unexpected body: {body}")

        # Check /
        start = time.perf_counter()
        req_root = urllib.request.Request(root_url, headers={"User-Agent": "OMS-HealthCheck/1.0"})
        with urllib.request.urlopen(req_root, timeout=3.0) as resp_root:
            elapsed_root = (time.perf_counter() - start) * 1000
            status_code_root = resp_root.status
            body_root = json.loads(resp_root.read().decode())
            if status_code_root == 200:
                messages.append(f"  [{GREEN}PASS{RESET}] GET {root_url} -> 200 OK ({elapsed_root:.1f}ms) [{body_root.get('name')}]")

        return True, messages
    except Exception as exc:
        messages.append(f"  [{YELLOW}NOTE{RESET}] Live server HTTP probe skipped or unreachable at {base_url} ({exc}).")
        messages.append(f"         (Start server with 'python scripts/run_dev.py' to test HTTP responses)")
        return True, messages


def main():
    parser = argparse.ArgumentParser(description="Paradox Sports OMS Server & Production Readiness Check")
    parser.add_argument("--url", help="Base URL of running server to probe (default: from settings)", default=None)
    parser.add_argument("--skip-http", action="store_true", help="Skip live HTTP service probe")
    args = parser.parse_args()

    print("\n" + "=" * 75)
    print(f"{BOLD}PARADOX SPORTS OMS — SERVER & PRODUCTION READINESS CHECK{RESET}")
    print("=" * 75)

    settings = get_settings()
    overall_pass = True

    # 1. Configuration
    print(f"\n{BOLD}[1/5] Application Configuration & Security{RESET}")
    ok_cfg, msgs_cfg = check_configuration(settings)
    for m in msgs_cfg:
        print(m)
    if not ok_cfg:
        overall_pass = False

    # 2. Database Connection
    print(f"\n{BOLD}[2/5] Database Connectivity (PostgreSQL){RESET}")
    ok_db, msgs_db = check_database()
    for m in msgs_db:
        print(m)
    if not ok_db:
        overall_pass = False

    # 3. Database Migrations
    print(f"\n{BOLD}[3/5] Schema Migrations (Alembic){RESET}")
    ok_mig, msgs_mig = check_migrations()
    for m in msgs_mig:
        print(m)
    if not ok_mig:
        overall_pass = False

    # 4. Entity Integrity
    print(f"\n{BOLD}[4/5] Core Database Entities & RBAC{RESET}")
    ok_ent, msgs_ent = check_entities()
    for m in msgs_ent:
        print(m)
    if not ok_ent:
        overall_pass = False

    # 5. HTTP Probes
    if not args.skip_http:
        probe_url = args.url or f"http://{settings.HOST}:{settings.PORT}"
        print(f"\n{BOLD}[5/5] Live HTTP Endpoint Probes ({probe_url}){RESET}")
        _, msgs_http = check_http_endpoints(probe_url)
        for m in msgs_http:
            print(m)

    # Summary
    print("\n" + "=" * 75)
    if overall_pass:
        print(f"{GREEN}{BOLD}STATUS: ALL CRITICAL READINESS CHECKS PASSED{RESET}")
        print("The application backend and database are ready for operation.")
    else:
        print(f"{RED}{BOLD}STATUS: ONE OR MORE CRITICAL CHECKS FAILED{RESET}")
        print("Please review the errors above before proceeding with deployment.")
    print("=" * 75 + "\n")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
