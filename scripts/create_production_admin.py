#!/usr/bin/env python3
"""
Production Administrator Provisioning Tool
Paradox Sports Operations Management System (OMS)

A secure, interactive CLI utility to create an initial or additional
System Administrator account in production environments.

Guarantees:
- Validates password complexity per production security policies.
- Secure masked password entry (getpass) with confirmation check.
- Strictly checks existing database records (prevents hijacking or accidental overwrite).
- Assigns full CANONICAL ADMIN RBAC permissions.
- Creates an immutable audit record in PostgreSQL.
- Zero mock / fake seed data.
"""

import argparse
import getpass
import os
import re
import sys
from typing import Optional
import uuid
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, AccountStatus
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.organization import Organization, Vertical, VerticalStatus, UserVertical
from app.models.audit import AuditLog
from app.services.rbac_service import (
    CANONICAL_ROLES,
    CORE_PERMISSIONS,
    ensure_canonical_roles_and_permissions,
)


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{3,50}$")


def validate_username(username: str) -> bool:
    return bool(USERNAME_REGEX.match(username.strip()))


def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_password_complexity(password: str) -> tuple[bool, str]:
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character (!@#$%^&*...)."
    return True, ""


def ensure_rbac_foundation(db) -> tuple[Role, Organization, Optional[Vertical]]:
    """Ensures base organization, optional primary vertical, and ADMIN role exist."""
    # 1. Organization
    stmt = select(Organization).limit(1)
    org = db.scalar(stmt)
    if not org:
        org = Organization(
            id=uuid.uuid4(),
            name="Paradox Sports Department",
            code="PARADOX_SPORTS",
            description="Authoritative Sports Department Organization",
        )
        db.add(org)
        db.flush()

    # 2. Primary Vertical (use existing if available, else None)
    stmt = select(Vertical).where(Vertical.organization_id == org.id).limit(1)
    vertical = db.scalar(stmt)

    # 3. Canonical Roles & Permissions Registry
    role_map = ensure_canonical_roles_and_permissions(db)
    admin_role = role_map["ADMIN"]

    db.flush()
    return admin_role, org, vertical


def create_admin_account():
    parser = argparse.ArgumentParser(description="Secure Production Administrator Provisioning CLI")
    parser.add_argument("--username", help="Admin account username", default=None)
    parser.add_argument("--email", help="Admin account email address", default=None)
    parser.add_argument("--full-name", help="Administrator full name", default=None)
    parser.add_argument("--password", help="Admin account password (prompted securely if omitted)", default=None)
    parser.add_argument("--non-interactive", action="store_true", dest="non_interactive", help="Fail if required fields are missing without prompting")

    args = parser.parse_args()

    print("\n" + "=" * 75)
    print("PARADOX SPORTS OMS — PRODUCTION ADMINISTRATOR CREATION TOOL")
    print("=" * 75)

    db = SessionLocal()

    try:
        # 1. Gather Username
        username = args.username
        if not username:
            if args.non_interactive:
                print("[-] Error: --username is required in non-interactive mode.", file=sys.stderr)
                sys.exit(1)
            while True:
                username = input("\n[?] Enter Admin Username (3-50 chars, alphanumeric/underscore): ").strip()
                if validate_username(username):
                    break
                print("[-] Invalid username format. Must be 3-50 alphanumeric characters or underscores.")

        username = username.strip().lower()

        # Database Check: Username Collision
        existing_by_user = db.scalar(select(User).where(User.username == username))
        if existing_by_user:
            print(f"\n[-] SECURITY ALERT: A user with username '{username}' ALREADY EXISTS in the database.")
            print("[-] Provisioning aborted to prevent unauthorized credential overwrite or account hijacking.")
            print(f"[-] Existing Account ID: {existing_by_user.id} (Status: {existing_by_user.account_status.value})")
            sys.exit(1)

        # 2. Gather Email
        email = args.email
        if not email:
            if args.non_interactive:
                print("[-] Error: --email is required in non-interactive mode.", file=sys.stderr)
                sys.exit(1)
            while True:
                email = input("[?] Enter Admin Email Address: ").strip()
                if validate_email(email):
                    break
                print("[-] Invalid email address format. Example: admin@paradoxsports.org")

        email = email.strip().lower()

        # Database Check: Email Collision
        existing_by_email = db.scalar(select(User).where(User.email == email))
        if existing_by_email:
            print(f"\n[-] SECURITY ALERT: A user with email '{email}' ALREADY EXISTS in the database.")
            print("[-] Provisioning aborted to prevent unauthorized credential overwrite or account hijacking.")
            sys.exit(1)

        # 3. Gather Full Name
        full_name = args.full_name
        if not full_name:
            if args.non_interactive:
                full_name = "System Administrator"
            else:
                full_name = input("[?] Enter Full Name: ").strip()
                if not full_name:
                    full_name = "System Administrator"

        # 4. Gather Secure Password
        password = args.password
        if password:
            is_valid, err_msg = validate_password_complexity(password)
            if not is_valid:
                print(f"[-] Weak password: {err_msg}", file=sys.stderr)
                sys.exit(1)
        else:
            if args.non_interactive:
                print("[-] Error: --password is required in non-interactive mode.", file=sys.stderr)
                sys.exit(1)
            while True:
                password = getpass.getpass("\n[?] Enter Secure Password (min 10 chars, upper, lower, digit, special): ")
                is_valid, err_msg = validate_password_complexity(password)
                if not is_valid:
                    print(f"[-] Weak password: {err_msg}")
                    continue

                password_confirm = getpass.getpass("[?] Confirm Password: ")
                if password != password_confirm:
                    print("[-] Passwords do not match. Please try again.")
                    continue

                break

        # 5. Provision in Database
        print("\n[*] Initializing RBAC foundation and verifying schema...")
        admin_role, org, vertical = ensure_rbac_foundation(db)

        new_user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            account_status=AccountStatus.ACTIVE,
        )
        db.add(new_user)
        db.flush()

        # Assign ADMIN Role
        user_role = UserRole(
            user_id=new_user.id,
            role_id=admin_role.id,
        )
        db.add(user_role)

        # Assign Primary Vertical (if a vertical exists in the database)
        if vertical:
            user_vertical = UserVertical(
                user_id=new_user.id,
                vertical_id=vertical.id,
                is_primary=True,
            )
            db.add(user_vertical)

        # Record Immutable Audit Trail
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            actor_id=new_user.id,
            action="ADMIN_ACCOUNT_PROVISIONED",
            resource_type="USER",
            resource_id=str(new_user.id),
            outcome="SUCCESS",
            details={
                "username": username,
                "email": email,
                "full_name": full_name,
                "role": "ADMIN",
                "vertical": vertical.name if vertical else "None",
                "provisioned_via": "CLI_TOOL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(audit_entry)

        db.commit()

        print("\n" + "=" * 75)
        print("ADMINISTRATOR ACCOUNT PROVISIONED SUCCESSFULLY!")
        print("=" * 75)
        print(f"  User ID:        {new_user.id}")
        print(f"  Username:       {new_user.username}")
        print(f"  Email:          {new_user.email}")
        print(f"  Full Name:      {new_user.full_name}")
        print(f"  Role:           ADMIN (Full Permissions Granted)")
        print(f"  Status:         ACTIVE")
        print(f"  Audit Log ID:   {audit_entry.id}")
        print("=" * 75)
        print("\nYou can now sign in at the production / development login page.")
        print("=" * 75 + "\n")

    except Exception as exc:
        db.rollback()
        print(f"\n[-] FATAL ERROR: Account provisioning failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_account()
