"""
RBAC & Permission Resolution Service
Server-authoritative role assignment, permission querying, and effective permission calculation.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.rbac import Permission, Role, RolePermission, UserPermissionOverride, UserRole

logger = get_logger(__name__)

# In-memory effective permissions cache: user_id -> (effective_perms_set, expiry_mono)
# Eliminates redundant DB queries for permission checks across concurrent API routes.
_USER_PERMS_CACHE: Dict[uuid.UUID, Tuple[Set[str], float]] = {}


def invalidate_perm_cache(user_id: Optional[uuid.UUID] = None) -> None:
    """Invalidates effective permissions cache for a specific user or globally."""
    if user_id:
        _USER_PERMS_CACHE.pop(user_id, None)
    else:
        _USER_PERMS_CACHE.clear()

CANONICAL_ROLES = [
    ("ADMIN", "System Administrator with full organizational access"),
    ("SPORTS_CORE", "Sports Department Core Executive Leadership"),
    ("DEPUTY_CORE", "Deputy Core Executive Member"),
    ("SUPER_COORDINATOR", "Super Coordinator managing multiple verticals"),
    ("COORDINATOR", "Vertical and Operational Coordinator"),
    ("VOLUNTEER", "Operational Volunteer Member"),
    ("EVENT_TEAM", "Designated Event Team Member"),
]

CORE_PERMISSIONS = [
    # Users
    ("users.read", "View user accounts and operational profiles", "users"),
    ("users.create", "Create new operational user accounts", "users"),
    ("users.update", "Update user accounts and credentials", "users"),
    ("users.disable", "Disable or suspend user accounts", "users"),
    # Roles & Permissions
    ("roles.read", "View canonical roles and permission sets", "roles"),
    ("roles.manage", "Assign roles to user accounts", "roles"),
    ("permissions.read", "View permission registry", "permissions"),
    ("permissions.manage", "Set explicit permission overrides", "permissions"),
    # Organization
    ("organization.read", "View organization profile and settings", "organization"),
    ("organization.manage", "Modify organization configuration", "organization"),
    # Verticals
    ("verticals.read", "View vertical divisions and assignments", "verticals"),
    ("verticals.create", "Create new vertical divisions", "verticals"),
    ("verticals.update", "Modify vertical divisions and status", "verticals"),
    ("verticals.disable", "Disable vertical divisions", "verticals"),
    ("verticals.assign", "Assign users to vertical divisions", "verticals"),
    # Audit & Security
    ("audit.read", "View immutable audit records and security logs", "audit"),
    ("system.read", "View system health and diagnostics", "system"),
    # Tasks (Phase 3)
    ("tasks.read", "View master tasks and operational workloads", "tasks"),
    ("tasks.create", "Create master tasks", "tasks"),
    ("tasks.update", "Update master tasks details", "tasks"),
    ("tasks.assign", "Assign tasks to users within vertical", "tasks"),
    ("tasks.transition", "Transition task status and completion", "tasks"),
    # Master Calendar (Phase 3)
    ("calendar.read", "View master calendar activities", "calendar"),
    ("calendar.create", "Create master calendar entries", "calendar"),
    ("calendar.update", "Update master calendar entries", "calendar"),
    # Issues & Escalations (Phase 3)
    ("issues.read", "View issue register entries", "issues"),
    ("issues.create", "Raise issues and problem tickets", "issues"),
    ("issues.update", "Update issue details and resolutions", "issues"),
    ("issues.escalate", "Escalate issues to leadership", "issues"),
    ("issues.confidential.read", "View confidential sensitivity issues", "issues"),
    # Daily & Weekly Work Reports (Phase 3)
    ("reports.read", "View daily work reports", "reports"),
    ("reports.submit", "Submit daily work reports", "reports"),
    ("reports.review", "Review, return or flag daily work reports", "reports"),
    ("reports.weekly.read", "View weekly operational reports", "reports"),
    ("reports.weekly.submit", "Submit weekly operational reports", "reports"),
    ("reports.weekly.review", "Review weekly operational reports", "reports"),
    # Events & Readiness (Phase 4)
    ("events.read", "View events, rosters and operational dashboards", "events"),
    ("events.create", "Create events and schedules", "events"),
    ("events.update", "Update event details and resources", "events"),
    ("events.transition", "Transition event lifecycle status", "events"),
    ("events.team.manage", "Assign/remove team members and designate POCs", "events"),
    ("events.poc.manage", "Assign and manage event POC groups", "events"),
    ("event_teams.read", "View event team profiles", "events"),
    ("event_teams.manage", "Create and manage event team accounts and profiles", "events"),
    ("events.readiness.manage", "Update readiness checklist items", "events"),
    # Requirements (Phase 4)
    ("requirements.read", "View cross-vertical requirements", "requirements"),
    ("requirements.create", "Raise cross-vertical operational requirements", "requirements"),
    ("requirements.assign", "Assign requirements to vertical members", "requirements"),
    ("requirements.transition", "Update requirement status and resolutions", "requirements"),
    ("requirements.message", "Post operational messages on requirements", "requirements"),
    # Meetings (Phase 4)
    ("meetings.read", "View operational meetings and rosters", "meetings"),
    ("meetings.create", "Schedule operational meetings", "meetings"),
    ("meetings.update", "Update, reschedule or cancel meetings", "meetings"),
    ("meetings.rsvp", "Respond and RSVP to meeting invitations", "meetings"),
    # Advanced Forms (Phase 4)
    ("forms.read", "View form definitions and submissions", "forms"),
    ("forms.create", "Create new form definitions and schemas", "forms"),
    ("forms.update", "Update draft forms and versions", "forms"),
    ("forms.publish", "Publish immutable form versions", "forms"),
    ("forms.submit", "Submit responses to published forms", "forms"),
    ("forms.review", "Review and approve form submissions", "forms"),
    # Announcements (Phase 5)
    ("announcements.read", "View announcements within authorized scope", "announcements"),
    ("announcements.create", "Draft new broadcast announcements", "announcements"),
    ("announcements.update", "Update draft announcements", "announcements"),
    ("announcements.publish", "Publish announcements to organization or vertical", "announcements"),
    ("announcements.archive", "Archive expired announcements", "announcements"),
    # Directives & Compliance (Phase 5)
    ("directives.read", "View operational directives within authorized scope", "directives"),
    ("directives.create", "Draft operational directives", "directives"),
    ("directives.update", "Update draft directives", "directives"),
    ("directives.issue", "Issue binding directives to organization or vertical", "directives"),
    ("directives.acknowledge", "Acknowledge received directives", "directives"),
    # Notifications (Phase 5)
    ("notifications.read", "Read personal attention notifications", "notifications"),
    ("notifications.manage", "Dismiss and mark notifications as read", "notifications"),
    # Communication Tracker (Phase 5)
    ("communications.read", "View operational communication records", "communications"),
    ("communications.create", "Record official communications", "communications"),
    ("communications.update", "Update communication log entries", "communications"),
    # Ownership Transfers (Phase 5)
    ("transfers.read", "View resource ownership transfer requests", "transfers"),
    ("transfers.request", "Initiate ownership transfer for a resource", "transfers"),
    ("transfers.approve", "Review, approve, or reject ownership transfers", "transfers"),
    # System Configuration (Phase 5)
    ("config.read", "View system configuration parameters", "config"),
    ("config.update", "Update system configuration settings", "config"),
    # Operational Analytics & Reporting (Phase 5)
    ("analytics.read", "View operational analytics and dashboards", "analytics"),
    ("analytics.admin", "View organization-wide administrative analytics", "analytics"),
    ("reports.admin", "Generate and export administrative reports", "reports"),
]

DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "ADMIN": [code for code, _, _ in CORE_PERMISSIONS],
    "SPORTS_CORE": [
        code for code, _, _ in CORE_PERMISSIONS
        if code not in ("system.read", "config.update")
    ],
    "DEPUTY_CORE": [
        code for code, _, _ in CORE_PERMISSIONS
        if code not in ("system.read", "config.read", "config.update", "analytics.admin", "reports.admin", "users.disable", "verticals.disable")
    ],
    "SUPER_COORDINATOR": [
        "users.read", "verticals.read", "verticals.assign",
        "tasks.read", "tasks.create", "tasks.update", "tasks.assign", "tasks.transition",
        "calendar.read", "calendar.create", "calendar.update",
        "issues.read", "issues.create", "issues.update", "issues.escalate",
        "reports.read", "reports.submit", "reports.review", "reports.weekly.read", "reports.weekly.submit", "reports.weekly.review",
        "events.read", "events.update", "events.team.manage", "events.poc.manage", "event_teams.read", "events.readiness.manage",
        "requirements.read", "requirements.create", "requirements.assign", "requirements.transition", "requirements.message",
        "meetings.read", "meetings.create", "meetings.update", "meetings.rsvp",
        "forms.read", "forms.create", "forms.update", "forms.publish", "forms.submit", "forms.review",
        "announcements.read", "announcements.create", "announcements.update", "announcements.publish",
        "directives.read", "directives.acknowledge",
        "notifications.read", "notifications.manage",
        "communications.read", "communications.create", "communications.update",
        "transfers.read", "transfers.request", "transfers.approve",
        "analytics.read",
    ],
    "COORDINATOR": [
        "users.read", "verticals.read",
        "tasks.read", "tasks.create", "tasks.update", "tasks.assign", "tasks.transition",
        "calendar.read", "calendar.create", "calendar.update",
        "issues.read", "issues.create", "issues.update", "issues.escalate",
        "reports.read", "reports.submit", "reports.review", "reports.weekly.read", "reports.weekly.submit",
        "events.read", "event_teams.read", "events.readiness.manage",
        "requirements.read", "requirements.create", "requirements.assign", "requirements.transition", "requirements.message",
        "meetings.read", "meetings.create", "meetings.update", "meetings.rsvp",
        "forms.read", "forms.submit", "forms.review",
        "announcements.read", "announcements.create",
        "directives.read", "directives.acknowledge",
        "notifications.read", "notifications.manage",
        "communications.read", "communications.create",
        "transfers.read", "transfers.request",
        "analytics.read",
    ],
    "VOLUNTEER": [
        "users.read", "verticals.read",
        "tasks.read", "tasks.transition",
        "calendar.read",
        "issues.read", "issues.create",
        "reports.read", "reports.submit",
        "events.read",
        "requirements.read", "requirements.message",
        "meetings.read", "meetings.rsvp",
        "forms.read", "forms.submit",
        "announcements.read",
        "directives.read", "directives.acknowledge",
        "notifications.read", "notifications.manage",
    ],
    "EVENT_TEAM": [
        "events.read",
        "event_teams.read",
        "requirements.read", "requirements.create", "requirements.message",
        "meetings.read", "meetings.rsvp",
        "forms.read", "forms.submit",
        "announcements.read",
        "directives.read", "directives.acknowledge",
        "notifications.read", "notifications.manage",
    ],
}


def ensure_canonical_roles_and_permissions(db: Session) -> Dict[str, Role]:
    """
    Ensures all 84 permissions, 7 canonical roles, and baseline role-permission mappings
    exist in the database. Idempotent and safe to run on every startup or migration.
    """
    perm_map: Dict[str, Permission] = {}
    for code, desc, cat in CORE_PERMISSIONS:
        stmt = select(Permission).where(Permission.code == code)
        perm = db.scalar(stmt)
        if not perm:
            perm = Permission(id=uuid.uuid4(), code=code, description=desc, category=cat)
            db.add(perm)
            db.flush()
        perm_map[code] = perm

    role_map: Dict[str, Role] = {}
    for rname, rdesc in CANONICAL_ROLES:
        stmt = select(Role).where(Role.name == rname)
        role = db.scalar(stmt)
        if not role:
            role = Role(id=uuid.uuid4(), name=rname, description=rdesc, is_system=True)
            db.add(role)
            db.flush()
        role_map[rname] = role

        # Ensure baseline permissions for this role
        assigned_codes = DEFAULT_ROLE_PERMISSIONS.get(rname, [])
        for pcode in assigned_codes:
            perm = perm_map.get(pcode)
            if perm:
                stmt_rp = select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
                if not db.scalar(stmt_rp):
                    db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    db.flush()
    return role_map


class RbacService:
    """Manages roles, permissions, and calculates server-authoritative effective permissions."""

    def __init__(self, db: Session):
        self.db = db

    def get_role_by_id(self, role_id: uuid.UUID) -> Role:
        """Retrieves role by UUID."""
        stmt = select(Role).where(Role.id == role_id)
        role = self.db.scalar(stmt)
        if not role:
            raise EntityNotFoundException("Role", str(role_id))
        return role

    def get_role_by_name(self, name: str) -> Role:
        """Retrieves role by canonical name."""
        stmt = select(Role).where(Role.name == name)
        role = self.db.scalar(stmt)
        if not role:
            raise EntityNotFoundException("Role", name)
        return role

    def list_roles(self) -> List[Role]:
        """Lists all roles with permissions preloaded."""
        stmt = select(Role).options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
        return list(self.db.scalars(stmt).all())

    def list_permissions(self) -> List[Permission]:
        """Lists all system permissions."""
        stmt = select(Permission).order_by(Permission.category, Permission.code)
        return list(self.db.scalars(stmt).all())

    def get_user_roles(self, user_id: uuid.UUID) -> List[Role]:
        """Returns list of active roles assigned to a user."""
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(self.db.scalars(stmt).all())

    def assign_roles(self, user_id: uuid.UUID, role_ids: List[uuid.UUID]) -> List[Role]:
        """
        Replaces user's assigned roles with the provided role IDs.
        Validates all role IDs exist.
        """
        # Deduplicate role_ids
        unique_role_ids = list(dict.fromkeys(role_ids))

        # Validate roles exist
        roles = []
        for rid in unique_role_ids:
            role = self.get_role_by_id(rid)
            roles.append(role)

        # Delete existing mappings
        self.db.execute(delete(UserRole).where(UserRole.user_id == user_id))

        # Insert new mappings
        for role in roles:
            mapping = UserRole(user_id=user_id, role_id=role.id)
            self.db.add(mapping)

        self.db.flush()
        invalidate_perm_cache(user_id)
        logger.info(f"Assigned roles {[r.name for r in roles]} to user {user_id}")
        return roles

    def get_effective_permissions(self, user_id: uuid.UUID) -> Set[str]:
        """
        Server-authoritative effective permission calculation:
        Effective = (Role Permissions + Explicit Grants) - Explicit Revokes
        ADMIN role automatically possesses ALL system permissions.
        Uses in-memory caching to eliminate redundant database queries on concurrent requests.
        """
        now_mono = time.monotonic()
        cached = _USER_PERMS_CACHE.get(user_id)
        if cached and now_mono < cached[1]:
            return cached[0]

        user_roles = self.get_user_roles(user_id)
        role_names = {r.name for r in user_roles}

        # If user has ADMIN role, return all available permission codes immediately
        if "ADMIN" in role_names:
            admin_perms = set(DEFAULT_ROLE_PERMISSIONS.get("ADMIN", [code for code, _, _ in CORE_PERMISSIONS]))
            _USER_PERMS_CACHE[user_id] = (admin_perms, now_mono + 60.0)
            return admin_perms

        # 1. Collect permissions from all assigned roles
        role_ids = [r.id for r in user_roles]
        role_perm_codes: Set[str] = set()

        if role_ids:
            stmt = (
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id.in_(role_ids))
            )
            role_perm_codes = set(self.db.scalars(stmt).all())

        # 2. Query explicit user permission overrides
        override_stmt = (
            select(Permission.code, UserPermissionOverride.is_granted)
            .join(Permission, Permission.id == UserPermissionOverride.permission_id)
            .where(UserPermissionOverride.user_id == user_id)
        )
        overrides = self.db.execute(override_stmt).all()

        explicit_grants = {code for code, is_granted in overrides if is_granted}
        explicit_revokes = {code for code, is_granted in overrides if not is_granted}

        # 3. Compute final effective set
        effective = (role_perm_codes | explicit_grants) - explicit_revokes
        _USER_PERMS_CACHE[user_id] = (effective, now_mono + 60.0)
        return effective

    def has_permission(self, user_id: uuid.UUID, permission_code: str) -> bool:
        """Checks if a user has a specific effective permission."""
        return permission_code in self.get_effective_permissions(user_id)

    def set_permission_overrides(
        self,
        user_id: uuid.UUID,
        overrides: List[Dict[str, Any]],
    ) -> None:
        """
        Sets explicit permission overrides (grants or revokes) for a specific user.
        """
        # Delete existing overrides
        self.db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id == user_id))

        for item in overrides:
            perm_id = item["permission_id"]
            is_granted = item["is_granted"]
            # Validate permission exists
            stmt = select(Permission).where(Permission.id == perm_id)
            if not self.db.scalar(stmt):
                raise EntityNotFoundException("Permission", str(perm_id))

            override = UserPermissionOverride(
                user_id=user_id,
                permission_id=perm_id,
                is_granted=is_granted,
            )
            self.db.add(override)

        self.db.flush()
        invalidate_perm_cache(user_id)
        logger.info(f"Updated permission overrides for user {user_id}")
