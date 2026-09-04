"""
Audience Resolution Service (Phase 10E Canonical)
Resolves complex audience selection criteria into a deduplicated set of active user IDs.
Supports:
- Vertical selection (A OR B)
- Role selection (Role A OR Role B)
- Vertical + Role combination ((A OR B) AND (Role A OR Role B))
- All Users broadcast (with caller permission validation)
- Individual users (username, full_name, email)
- Deduplication and server-side authorization enforcement
"""

import uuid
from typing import List, Optional, Set
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.organization import UserVertical, Vertical
from app.models.rbac import Role, UserRole
from app.models.user import AccountStatus, User
from app.schemas.organization import (
    AudienceResolveRequest,
    AudienceResolveResponse,
    ResolvedUserSummary,
)
from app.services.authority_service import AuthorityService
from app.services.organization_service import OrganizationService
from app.services.rbac_service import RbacService

logger = get_logger(__name__)


class AudienceService:
    def __init__(self, db: Session):
        self.db = db
        self.authority = AuthorityService(db)
        self.rbac = RbacService(db)
        self.org = OrganizationService(db)

    def resolve_audience(
        self,
        request: AudienceResolveRequest,
        actor: User,
    ) -> AudienceResolveResponse:
        """
        Resolves an AudienceResolveRequest into active user IDs and summaries.
        Strictly enforces caller authority and server-side isolation.
        """
        is_exec = self.authority.is_executive(actor.id)
        is_admin = self.authority.is_admin(actor.id)
        is_exec_or_admin = is_exec or is_admin

        actor_vert_ids = set(self.authority.get_user_vertical_ids(actor.id))

        group_uids: Set[uuid.UUID] = set()
        summary_parts: List[str] = []
        is_all = False

        # -------------------------------------------------------------
        # 1. All Users Selection
        # -------------------------------------------------------------
        if request.all_users:
            if not is_exec_or_admin:
                logger.warning(
                    f"Audience resolution denied: Actor '{actor.username}' unauthorized for ALL_USERS"
                )
                raise ForbiddenException("You are not authorized to target the entire organization")

            is_all = True
            all_stmt = select(User.id).where(User.account_status == AccountStatus.ACTIVE)
            all_uids = set(self.db.scalars(all_stmt).all())
            group_uids.update(all_uids)
            summary_parts.append("Entire Organization")

        # -------------------------------------------------------------
        # 2. Vertical Selection Validation
        # -------------------------------------------------------------
        validated_vert_ids: List[uuid.UUID] = []
        vert_names: List[str] = []
        if request.vertical_ids:
            for vid in request.vertical_ids:
                v = self.org.get_vertical(vid)
                if not v:
                    raise ValidationException(f"Vertical division '{vid}' does not exist")
                if not is_exec_or_admin and v.id not in actor_vert_ids:
                    logger.warning(
                        f"Cross-vertical audience denied: Actor '{actor.username}' not in vertical '{v.name}'"
                    )
                    raise ForbiddenException(f"You do not have authorization to target vertical '{v.name}'")
                validated_vert_ids.append(v.id)
                vert_names.append(v.name)

        # -------------------------------------------------------------
        # 3. Role Selection Validation
        # -------------------------------------------------------------
        validated_roles: List[str] = []
        if request.role_ids:
            for r_id in request.role_ids:
                r_clean = r_id.strip().upper()
                role_obj = self.db.scalar(select(Role).where(Role.name == r_clean))
                if not role_obj:
                    # Check if UUID string passed
                    try:
                        role_uuid = uuid.UUID(r_id)
                        role_obj = self.db.get(Role, role_uuid)
                    except ValueError:
                        pass
                if not role_obj:
                    raise ValidationException(f"Role '{r_id}' is not a valid canonical role")
                if role_obj.name == "ADMIN":
                    raise ValidationException("The ADMIN role is prohibited from being targeted via the Universal Selector")
                validated_roles.append(role_obj.name)

        # -------------------------------------------------------------
        # 4. Group Resolution Logic: Verticals and Roles
        # -------------------------------------------------------------
        if not is_all and (validated_vert_ids or validated_roles):
            if request.usage == "assignment" or getattr(request, "union_groups", False):
                # Union mode for assignment combinations: (Members of Verticals) UNION (Members of Roles)
                if validated_vert_ids:
                    stmt_v = (
                        select(User.id)
                        .join(UserVertical, User.id == UserVertical.user_id)
                        .where(
                            User.account_status == AccountStatus.ACTIVE,
                            UserVertical.vertical_id.in_(validated_vert_ids),
                        )
                    )
                    group_uids.update(set(self.db.scalars(stmt_v).all()))
                    summary_parts.append(f"Verticals ({', '.join(vert_names)})")

                if validated_roles:
                    stmt_r = (
                        select(User.id)
                        .join(UserRole, User.id == UserRole.user_id)
                        .join(Role, UserRole.role_id == Role.id)
                        .where(
                            User.account_status == AccountStatus.ACTIVE,
                            Role.name.in_(validated_roles),
                        )
                    )
                    group_uids.update(set(self.db.scalars(stmt_r).all()))
                    summary_parts.append(f"Roles ({', '.join(validated_roles)})")

            elif validated_vert_ids and validated_roles:
                # Intersect mode: (V1 OR V2 ...) AND (R1 OR R2 ...)
                stmt = (
                    select(User.id)
                    .join(UserVertical, User.id == UserVertical.user_id)
                    .join(UserRole, User.id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(
                        User.account_status == AccountStatus.ACTIVE,
                        UserVertical.vertical_id.in_(validated_vert_ids),
                        Role.name.in_(validated_roles),
                    )
                )
                combo_uids = set(self.db.scalars(stmt).all())
                group_uids.update(combo_uids)
                summary_parts.append(
                    f"({' OR '.join(vert_names)}) AND ({' OR '.join(validated_roles)})"
                )
            elif validated_vert_ids and not validated_roles:
                # Verticals only: V1 OR V2 ...
                stmt = (
                    select(User.id)
                    .join(UserVertical, User.id == UserVertical.user_id)
                    .where(
                        User.account_status == AccountStatus.ACTIVE,
                        UserVertical.vertical_id.in_(validated_vert_ids),
                    )
                )
                vert_uids = set(self.db.scalars(stmt).all())
                group_uids.update(vert_uids)
                summary_parts.append(f"{' OR '.join(vert_names)}")
            elif validated_roles and not validated_vert_ids:
                # Roles only: R1 OR R2 ...
                stmt = (
                    select(User.id)
                    .join(UserRole, User.id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.id)
                    .where(
                        User.account_status == AccountStatus.ACTIVE,
                        Role.name.in_(validated_roles),
                    )
                )
                # Scope to actor's vertical if non-executive
                if not is_exec_or_admin:
                    stmt = stmt.join(UserVertical, User.id == UserVertical.user_id).where(
                        UserVertical.vertical_id.in_(actor_vert_ids)
                    )
                role_uids = set(self.db.scalars(stmt).all())
                group_uids.update(role_uids)
                summary_parts.append(f"{' OR '.join(validated_roles)}")

        # -------------------------------------------------------------
        # 5. Individual User Selection & Authorization Verification
        # -------------------------------------------------------------
        individual_uids: Set[uuid.UUID] = set()
        if request.user_ids:
            for uid in request.user_ids:
                u = self.db.get(User, uid)
                if not u:
                    raise ValidationException(f"User with ID '{uid}' does not exist")
                if u.account_status != AccountStatus.ACTIVE:
                    raise ValidationException(f"User '{u.username}' is not an active account")

                u_roles = {r.name for r in self.rbac.get_user_roles(u.id)}
                if "ADMIN" in u_roles:
                    raise ValidationException(f"Administrator account '{u.username}' cannot be targeted via the Universal Selector")

                if not is_exec_or_admin:
                    u_vids = set(self.authority.get_user_vertical_ids(u.id))
                    # Must share at least one vertical with actor
                    if not (u_vids & actor_vert_ids):
                        logger.warning(
                            f"Audience bypass attempt: Actor '{actor.username}' tried to target user '{u.username}' outside vertical"
                        )
                        raise ForbiddenException(
                            f"User '{u.username}' ({u.id}) is outside your authorized operational scope"
                        )
                individual_uids.add(u.id)

            if individual_uids:
                summary_parts.append(f"{len(individual_uids)} individual user(s)")

        # -------------------------------------------------------------
        # 6. Final Deduplication
        # -------------------------------------------------------------
        final_uids = group_uids.union(individual_uids)

        # -------------------------------------------------------------
        # 7. Hydrate User Summaries for UI Preview
        # -------------------------------------------------------------
        users_detail: List[ResolvedUserSummary] = []
        if final_uids:
            hydrate_stmt = (
                select(User)
                .options(
                    selectinload(User.user_roles).selectinload(UserRole.role),
                    selectinload(User.user_verticals).selectinload(UserVertical.vertical),
                )
                .where(User.id.in_(final_uids))
                .order_by(User.full_name.asc(), User.username.asc())
            )
            hydrated_users = self.db.scalars(hydrate_stmt).all()
            for u in hydrated_users:
                r_names = [ur.role.name for ur in u.user_roles if ur.role]
                v_names = [uv.vertical.name for uv in u.user_verticals if uv.vertical]
                users_detail.append(
                    ResolvedUserSummary(
                        id=u.id,
                        username=u.username,
                        full_name=u.full_name,
                        email=u.email,
                        account_status=u.account_status.value,
                        roles=r_names,
                        verticals=v_names,
                    )
                )

        summary_text = " + ".join(summary_parts) if summary_parts else "No audience selected"
        summary_text += f" • {len(final_uids)} active user(s)"

        return AudienceResolveResponse(
            total_count=len(final_uids),
            user_ids=list(final_uids),
            users=users_detail,
            audience_summary=summary_text,
            is_all_users=is_all,
        )
