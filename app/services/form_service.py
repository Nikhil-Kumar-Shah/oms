"""
Advanced Forms, Versions, Distributions, Responses & Multi-Phase Review Workflow Service Layer
Paradox Sports OMS - Phase 11 Form & Response Workflow System
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.communication import NotificationType
from app.models.event import Event, EventStatus, EventTeamProfile, EventType

from app.models.form import (
    ChecklistStatus,
    Form,
    FormAudience,
    FormChecklistItem,
    FormDistribution,
    FormFieldType,
    FormResponse,
    FormResponseStatus,
    FormReviewer,
    FormStatus,
    FormVersion,
    FormWorkflowHistory,
)
from app.models.organization import UserVertical, Vertical
from app.models.rbac import Role, UserRole
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.user import User
from app.schemas.form import (
    ChecklistItemUpdate,
    DistributionSummaryResponse,
    FormCreate,
    FormDashboardStats,
    FormDistributeRequest,
    FormFieldSchema,
    FormResponseForwardRequest,
    FormResponseReviewRequest,
    FormResponseSaveDraft,
    FormResponseSubmit,
    FormSectionSchema,
    FormUpdate,
    FormVersionCreate,
    RecipientSummaryItem,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class FormService:
    """Manages Form Templates, Distributions, Independent Responses, Multi-Reviewer Checklists, and Workflow Lifecycles."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)


    def _get_user_roles(self, user: User) -> List[str]:
        if hasattr(user, "roles") and user.roles:
            return [r.name for r in user.roles]
        return [
            r.name
            for r in self.db.scalars(
                select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            ).all()
        ]

    def _get_user_vertical_ids(self, user: User) -> List[UUID]:
        return list(
            self.db.scalars(
                select(UserVertical.vertical_id).where(UserVertical.user_id == user.id)
            ).all()
        )

    # -------------------------------------------------------------
    # 1. FORM TEMPLATE CREATION & GOVERNANCE
    # -------------------------------------------------------------

    def create_form(self, data: FormCreate, owner_id: UUID, current_user: Optional[User] = None) -> Form:
        """Create a new Form Template. Strictly role-gated to ADMIN, SPORTS_CORE, DEPUTY_CORE, and SUPER_COORDINATOR."""
        if current_user:
            roles = self._get_user_roles(current_user)
            allowed_roles = {"ADMIN", "SPORTS_CORE", "DEPUTY_CORE", "SUPER_COORDINATOR"}
            if not any(r in allowed_roles for r in roles):
                raise ForbiddenException("Only executive leadership and super coordinators are authorized to create form templates.")

        if data.vertical_id:
            vert = self.db.get(Vertical, data.vertical_id)
            if not vert:
                raise ValidationException("Target vertical division not found")

        if data.event_id:
            event = self.db.get(Event, data.event_id)
            if not event:
                raise ValidationException("Target event not found")

        form = Form(
            name=data.name,
            description=data.description,
            purpose=data.purpose,
            instructions=data.instructions,
            category=data.category or "Operational",
            status=FormStatus.DRAFT,
            owner_id=owner_id,
            vertical_id=data.vertical_id,
            event_id=data.event_id,
            target_audience=data.target_audience,
            current_version_number=1,
        )
        self.db.add(form)
        self.db.flush()

        # Build structured sections and schema list
        sections_data: List[Dict[str, Any]] = []
        schema_fields: List[Dict[str, Any]] = []

        if data.sections:
            for idx, s in enumerate(data.sections):
                s_dict = s.model_dump()
                s_dict["ordering"] = idx + 1
                sections_data.append(s_dict)
                for f in s.fields:
                    schema_fields.append(f.model_dump())
        elif data.initial_schema:
            default_sec = {
                "id": "sec-1",
                "title": "General Details",
                "description": "Standard form questions",
                "ordering": 1,
                "fields": [f.model_dump() for f in data.initial_schema],
            }
            sections_data.append(default_sec)
            schema_fields = [f.model_dump() for f in data.initial_schema]

        review_config_json = (
            [rc.model_dump() for rc in data.review_config]
            if data.review_config
            else [
                {"phase_number": 1, "phase_name": "Phase 1: Initial Submission", "title": "Submitter Checklist", "description": "Verify all mandatory items provided", "role_label": "Submitter"},
                {"phase_number": 2, "phase_name": "Phase 2: POC Review", "title": "POC Operational Verification", "description": "Check technical correctness and references", "role_label": "POC"},
                {"phase_number": 3, "phase_name": "Phase 3: Vertical Sign-off", "title": "Vertical Coordinator Approval", "description": "Review and approve vertical alignment", "role_label": "Coordinator"},
                {"phase_number": 4, "phase_name": "Phase 4: Core Leadership Approval", "title": "Executive Final Approval", "description": "Final sports core sign-off", "role_label": "Sports Core"},
            ]
        )

        v1 = FormVersion(
            form_id=form.id,
            version_number=1,
            sections=sections_data,
            schema=schema_fields,
            review_config=review_config_json,
            transformation_config=data.transformation_config.model_dump() if data.transformation_config else None,
            is_published=False,
        )
        self.db.add(v1)
        self.db.flush()

        # Handle distribution_config & recipient_ids
        dist_config = dict(data.distribution_config or {})
        recipient_ids: List[UUID] = []
        if data.recipient_ids:
            recipient_ids = list(data.recipient_ids)
            dist_config["recipient_ids"] = [str(r) for r in recipient_ids]
        else:
            recipient_ids = self._resolve_audience_recipients(dist_config, current_user)
            if recipient_ids:
                dist_config["recipient_ids"] = [str(r) for r in recipient_ids]

        deadline = data.distribution_deadline
        if deadline:
            dist_config["deadline"] = deadline.isoformat()
        elif "deadline" in dist_config and dist_config["deadline"]:
            try:
                deadline = datetime.fromisoformat(str(dist_config["deadline"]))
            except Exception:
                pass

        dist_instructions = data.distribution_instructions
        if dist_instructions:
            dist_config["distribution_instructions"] = dist_instructions
        elif "distribution_instructions" in dist_config:
            dist_instructions = dist_config.get("distribution_instructions")

        form.distribution_config = dist_config

        if data.publish_and_distribute:
            if not recipient_ids:
                raise ValidationException("At least one recipient must be selected to publish and distribute the form.")

            v1.is_published = True
            v1.published_at = datetime.now(timezone.utc)
            v1.published_by_id = owner_id
            form.status = FormStatus.PUBLISHED

            self._execute_distribution(
                form=form,
                version=v1,
                recipient_ids=recipient_ids,
                distributor_id=owner_id,
                deadline=deadline,
                instructions=dist_instructions,
                current_user=current_user,
            )

        self.audit.log(
            action="FORM_CREATE",
            resource_type="FORM",
            resource_id=str(form.id),
            outcome="SUCCESS",
            actor_id=owner_id,
            details={"name": form.name, "purpose": form.purpose, "status": form.status.value},
        )
        logger.info(f"Created Form Template '{form.name}' (id={form.id}, status={form.status.value})")
        return form

    def get_form_by_id(self, form_id: UUID, current_user: Optional[User] = None) -> Form:
        form = self.db.scalar(
            select(Form)
            .where(Form.id == form_id)
            .options(
                selectinload(Form.owner),
                selectinload(Form.vertical),
                selectinload(Form.event),
                selectinload(Form.versions).selectinload(FormVersion.published_by),
                selectinload(Form.distributions),
                selectinload(Form.responses),
            )
        )
        if not form:
            raise EntityNotFoundException(f"Form with ID '{form_id}' not found")
        return form

    def list_forms(
        self,
        vertical_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        status: Optional[FormStatus] = None,
        category: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        workspace_tab: Optional[str] = None,  # my_created, templates, my_distributed, all
        current_user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Form], int]:
        stmt = select(Form).options(
            selectinload(Form.owner),
            selectinload(Form.vertical),
            selectinload(Form.event),
            selectinload(Form.versions),
            selectinload(Form.distributions),
            selectinload(Form.responses),
        )
        count_stmt = select(func.count(Form.id))

        if owner_id:
            stmt = stmt.where(Form.owner_id == owner_id)
            count_stmt = count_stmt.where(Form.owner_id == owner_id)
        if vertical_id:
            stmt = stmt.where(Form.vertical_id == vertical_id)
            count_stmt = count_stmt.where(Form.vertical_id == vertical_id)
        if event_id:
            stmt = stmt.where(Form.event_id == event_id)
            count_stmt = count_stmt.where(Form.event_id == event_id)
        if status:
            stmt = stmt.where(Form.status == status)
            count_stmt = count_stmt.where(Form.status == status)
        if category:
            stmt = stmt.where(Form.category == category)
            count_stmt = count_stmt.where(Form.category == category)

        # Tab-based filtering
        if current_user and workspace_tab:
            uid = current_user.id
            if workspace_tab == "my_created":
                stmt = stmt.where(Form.owner_id == uid)
                count_stmt = count_stmt.where(Form.owner_id == uid)
            elif workspace_tab == "templates":
                stmt = stmt.where(or_(Form.target_audience == FormAudience.ALL, Form.category.ilike("%template%"), Form.status == FormStatus.PUBLISHED))
                count_stmt = count_stmt.where(or_(Form.target_audience == FormAudience.ALL, Form.category.ilike("%template%"), Form.status == FormStatus.PUBLISHED))
            elif workspace_tab == "my_distributed":
                stmt = stmt.join(FormDistribution, FormDistribution.form_id == Form.id).where(FormDistribution.distributor_id == uid).distinct()
                count_stmt = select(func.count(func.distinct(Form.id))).select_from(Form).join(FormDistribution, FormDistribution.form_id == Form.id).where(FormDistribution.distributor_id == uid)
        elif current_user:
            roles = self._get_user_roles(current_user)
            if "EVENT_TEAM" in roles and "ADMIN" not in roles and "SPORTS_CORE" not in roles:
                profile = self.db.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == current_user.id))
                team_event_id = profile.event_id if profile else None
                event_filters = [Form.target_audience.in_([FormAudience.ALL, FormAudience.EVENT_TEAM])]
                if team_event_id is not None:
                    event_filters.append(Form.event_id == team_event_id)
                stmt = stmt.where(or_(*event_filters))
                count_stmt = count_stmt.where(or_(*event_filters))

        total = self.db.scalar(count_stmt) or 0
        forms = list(self.db.scalars(stmt.order_by(Form.created_at.desc()).offset(offset).limit(limit)).all())
        return forms, total


    def update_form(self, form_id: UUID, data: FormUpdate, actor_id: UUID, current_user: Optional[User] = None) -> Form:
        form = self.get_form_by_id(form_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if key not in ("sections", "distribution_config", "publish_and_distribute", "recipient_ids", "distribution_deadline", "distribution_instructions") and hasattr(form, key):
                setattr(form, key, value)

        # Merge distribution_config
        dist_config = dict(form.distribution_config or {})
        if data.distribution_config:
            dist_config.update(data.distribution_config)
        if data.recipient_ids is not None:
            dist_config["recipient_ids"] = [str(r) for r in data.recipient_ids]
        if data.distribution_deadline is not None:
            dist_config["deadline"] = data.distribution_deadline.isoformat()
        if data.distribution_instructions is not None:
            dist_config["distribution_instructions"] = data.distribution_instructions
        form.distribution_config = dist_config

        # Update sections/questions on the latest version if draft
        if data.sections and form.versions:
            target_v = form.versions[-1]
            if not target_v.is_published:
                sections_data = []
                schema_fields = []
                for idx, s in enumerate(data.sections):
                    s_dict = s.model_dump()
                    s_dict["ordering"] = idx + 1
                    sections_data.append(s_dict)
                    for f in s.fields:
                        schema_fields.append(f.model_dump())
                target_v.sections = sections_data
                target_v.schema = schema_fields

        # Handle publish & distribute
        if data.publish_and_distribute:
            recipient_ids: List[UUID] = []
            if data.recipient_ids:
                recipient_ids = list(data.recipient_ids)
            else:
                recipient_ids = self._resolve_audience_recipients(dist_config, current_user)
                if recipient_ids:
                    dist_config["recipient_ids"] = [str(r) for r in recipient_ids]

            if not recipient_ids:
                raise ValidationException("At least one recipient must be selected to publish and distribute the form.")

            target_v = form.versions[-1] if form.versions else None
            if not target_v:
                raise ValidationException("Form has no version to publish.")

            if not target_v.is_published:
                target_v.is_published = True
                target_v.published_at = datetime.now(timezone.utc)
                target_v.published_by_id = actor_id
            form.status = FormStatus.PUBLISHED

            existing_dist = self.db.scalar(
                select(FormDistribution).where(
                    FormDistribution.form_id == form.id,
                    FormDistribution.form_version_id == target_v.id,
                )
            )
            if not existing_dist:
                deadline = data.distribution_deadline
                if not deadline and dist_config.get("deadline"):
                    try:
                        deadline = datetime.fromisoformat(str(dist_config["deadline"]))
                    except Exception:
                        pass

                dist_instructions = data.distribution_instructions or dist_config.get("distribution_instructions")
                self._execute_distribution(
                    form=form,
                    version=target_v,
                    recipient_ids=recipient_ids,
                    distributor_id=actor_id,
                    deadline=deadline,
                    instructions=dist_instructions,
                    current_user=current_user,
                )

        self.audit.log(
            action="FORM_UPDATE",
            resource_type="FORM",
            resource_id=str(form.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=data.model_dump(exclude_unset=True, mode="json"),
        )
        return form

    # -------------------------------------------------------------
    # 2. IMMUTABLE VERSIONING
    # -------------------------------------------------------------

    def create_form_version(self, form_id: UUID, data: FormVersionCreate, actor_id: UUID) -> FormVersion:
        form = self.get_form_by_id(form_id)
        next_ver = form.current_version_number + 1
        form.current_version_number = next_ver

        sections_data: List[Dict[str, Any]] = []
        schema_fields: List[Dict[str, Any]] = []

        if data.sections:
            for idx, s in enumerate(data.sections):
                s_dict = s.model_dump()
                s_dict["ordering"] = idx + 1
                sections_data.append(s_dict)
                for f in s.fields:
                    schema_fields.append(f.model_dump())
        elif data.schema_fields:
            default_sec = {
                "id": "sec-1",
                "title": "General Details",
                "ordering": 1,
                "fields": [f.model_dump() for f in data.schema_fields],
            }
            sections_data.append(default_sec)
            schema_fields = [f.model_dump() for f in data.schema_fields]

        version = FormVersion(
            form_id=form.id,
            version_number=next_ver,
            sections=sections_data,
            schema=schema_fields,
            review_config=[rc.model_dump() for rc in data.review_config] if data.review_config else None,
            transformation_config=data.transformation_config.model_dump() if data.transformation_config else None,
            is_published=False,
        )
        self.db.add(version)
        self.db.flush()

        self.audit.log(
            action="FORM_VERSION_CREATE",
            resource_type="FORM_VERSION",
            resource_id=str(version.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"form_id": str(form.id), "version_number": next_ver},
        )
        return version

    def get_form_version(self, form_id: UUID, version_number: int) -> FormVersion:
        version = self.db.scalar(
            select(FormVersion).where(
                FormVersion.form_id == form_id,
                FormVersion.version_number == version_number,
            )
        )
        if not version:
            raise EntityNotFoundException(f"Version {version_number} of form '{form_id}' not found")
        return version

    def publish_form_version(self, form_id: UUID, version_number: int, actor_id: UUID) -> FormVersion:
        form = self.get_form_by_id(form_id)
        version = self.get_form_version(form.id, version_number)

        if not version:
            raise EntityNotFoundException(f"Version {version_number} of form '{form.name}' not found")

        version.is_published = True
        version.published_at = datetime.now(timezone.utc)
        version.published_by_id = actor_id
        form.status = FormStatus.PUBLISHED

        self.audit.log(
            action="FORM_VERSION_PUBLISH",
            resource_type="FORM_VERSION",
            resource_id=str(version.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"form_id": str(form.id), "version_number": version_number},
        )
        return version

    def get_latest_published_version(self, form_id: UUID) -> FormVersion:
        version = self.db.scalar(
            select(FormVersion)
            .where(FormVersion.form_id == form_id, FormVersion.is_published.is_(True))
            .order_by(FormVersion.version_number.desc())
            .limit(1)
        )
        if not version:
            raise ValidationException(f"Form '{form_id}' does not have any published version available for distribution/submission")
        return version

    def _resolve_audience_recipients(
        self,
        dist_config: Dict[str, Any],
        current_user: Optional[User],
    ) -> List[UUID]:
        """Resolves audience_items or direct recipient_ids from distribution_config to individual user UUIDs."""
        recipient_ids: List[UUID] = []
        if "recipient_ids" in dist_config and dist_config["recipient_ids"]:
            try:
                recipient_ids = [UUID(str(r)) for r in dist_config["recipient_ids"]]
            except Exception:
                pass
        if not recipient_ids and current_user:
            audience_items = dist_config.get("audience_items") or []
            if audience_items:
                try:
                    from app.services.audience_service import AudienceService
                    from app.schemas.organization import AudienceResolveRequest
                    aud_service = AudienceService(self.db)
                    req = AudienceResolveRequest(
                        all_users=any(it.get("type") in ("ALL", "ALL_USERS") or it.get("rawId") == "ALL" for it in audience_items),
                        vertical_ids=[UUID(it["rawId"]) for it in audience_items if it.get("type") == "VERTICAL" and it.get("rawId")],
                        role_ids=[it["rawId"] for it in audience_items if it.get("type") == "ROLE" and it.get("rawId")],
                        user_ids=[UUID(it["rawId"]) for it in audience_items if it.get("type") == "USER" and it.get("rawId")],
                        usage="assignment",
                    )
                    resolved = aud_service.resolve_audience(req, actor=current_user)
                    recipient_ids = [UUID(str(u)) for u in resolved.user_ids]
                except Exception as e:
                    logger.warning(f"Could not resolve audience items: {e}")
        return recipient_ids

    # -------------------------------------------------------------
    # 3. FORM DISTRIBUTION & MULTIPLE RESPONSE INSTANCES
    # -------------------------------------------------------------

    def _execute_distribution(
        self,
        form: Form,
        version: FormVersion,
        recipient_ids: List[UUID],
        distributor_id: UUID,
        deadline: Optional[datetime] = None,
        instructions: Optional[str] = None,
        current_user: Optional[User] = None,
        reviewers: Optional[List[Any]] = None,
    ) -> FormDistribution:
        """Core transactional distribution engine creating distributions, response instances, and initial review checklists."""
        if not recipient_ids:
            raise ValidationException("At least one recipient must be selected for form distribution.")

        recipients = list(self.db.scalars(select(User).where(User.id.in_(recipient_ids))).all())
        if len(recipients) != len(recipient_ids):
            found_ids = {r.id for r in recipients}
            missing = [str(rid) for rid in recipient_ids if rid not in found_ids]
            raise ValidationException(f"One or more recipient users not found: {missing}")

        distribution = FormDistribution(
            form_id=form.id,
            form_version_id=version.id,
            distributor_id=distributor_id,
            title=f"{form.name} Distribution",
            instructions=instructions or form.instructions,
            deadline=deadline,
            recipient_count=len(recipients),
        )
        self.db.add(distribution)
        self.db.flush()

        review_config_items: List[Dict[str, Any]] = version.review_config or []

        for recipient in recipients:
            profile = self.db.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == recipient.id))
            event_id = profile.event_id if profile else form.event_id
            event_team_profile_id = profile.id if profile else None

            resp = FormResponse(
                form_id=form.id,
                form_version_id=version.id,
                distribution_id=distribution.id,
                recipient_id=recipient.id,
                event_id=event_id,
                event_team_profile_id=event_team_profile_id,
                status=FormResponseStatus.ASSIGNED,
                response_data={},
                deadline=deadline,
                current_phase=1,
            )
            self.db.add(resp)
            self.db.flush()

            distributor_name = current_user.username if current_user else "Distributor"
            history = FormWorkflowHistory(
                response_id=resp.id,
                actor_id=distributor_id,
                action="DISTRIBUTED",
                from_status=None,
                to_status=FormResponseStatus.ASSIGNED.value,
                message=f"Form '{form.name}' assigned to @{recipient.username} by @{distributor_name}.",
                history_metadata={"distribution_id": str(distribution.id), "deadline": str(deadline) if deadline else None},
            )
            self.db.add(history)

            if review_config_items:
                for item_cfg in review_config_items:
                    chk = FormChecklistItem(
                        response_id=resp.id,
                        phase_number=item_cfg.get("phase_number", 1),
                        phase_name=item_cfg.get("phase_name", "Review Phase"),
                        title=item_cfg.get("title", "Verification Item"),
                        description=item_cfg.get("description"),
                        status=ChecklistStatus.PENDING,
                    )
                    self.db.add(chk)

            if reviewers:
                for r_input in reviewers:
                    rev = FormReviewer(
                        response_id=resp.id,
                        user_id=r_input.user_id,
                        role_label=r_input.role_label,
                        phase_number=r_input.phase_number,
                        status="PENDING",
                    )
                    self.db.add(rev)
                phase1_rev = next((r for r in reviewers if r.phase_number == 1), None)
                if phase1_rev:
                    resp.current_reviewer_id = phase1_rev.user_id

            if recipient.id != distributor_id:
                self.notif_service.create_notification(
                    recipient_id=recipient.id,
                    notification_type=NotificationType.FORM,
                    title=f"New Form Assigned: {form.name}",
                    message=f"You have been assigned to complete form '{form.name}'. Deadline: {deadline.strftime('%d %b %Y') if deadline else 'Not set'}.",
                    related_resource_type="FORM_RESPONSE",
                    related_resource_id=resp.id,
                )

        self.audit.log(
            action="FORM_DISTRIBUTION_CREATE",
            resource_type="FORM_DISTRIBUTION",
            resource_id=str(distribution.id),
            outcome="SUCCESS",
            actor_id=distributor_id,
            details={"form_id": str(form.id), "recipients_count": len(recipients)},
        )
        logger.info(f"Distributed form '{form.name}' to {len(recipients)} recipients (distribution_id={distribution.id})")
        return distribution

    def distribute_form(
        self,
        form_id: UUID,
        data: FormDistributeRequest,
        distributor_id: UUID,
        current_user: Optional[User] = None,
    ) -> FormDistribution:
        """
        Transactional Form Distribution.
        Distributes 1 published form template version across N recipients,
        generating N independent FormResponse records and initializing default review checklists.
        """
        form = self.get_form_by_id(form_id)
        version = self.get_latest_published_version(form_id)
        return self._execute_distribution(
            form=form,
            version=version,
            recipient_ids=data.recipient_ids,
            distributor_id=distributor_id,
            deadline=data.deadline,
            instructions=data.instructions,
            current_user=current_user,
            reviewers=data.reviewers,
        )

    def get_distribution_summary(
        self,
        form_id: Optional[UUID] = None,
        distribution_id: Optional[UUID] = None,
    ) -> DistributionSummaryResponse:
        """Aggregates distribution progress across all recipient response instances."""
        stmt = select(FormResponse).options(
            selectinload(FormResponse.recipient),
            selectinload(FormResponse.event),
            selectinload(FormResponse.checklist_items),
            selectinload(FormResponse.form),
            selectinload(FormResponse.form_version),
        )
        if distribution_id:
            stmt = stmt.where(FormResponse.distribution_id == distribution_id)
        elif form_id:
            stmt = stmt.where(FormResponse.form_id == form_id)
        else:
            raise ValidationException("Either form_id or distribution_id must be provided")

        responses = list(self.db.scalars(stmt).all())
        if not responses:
            form = self.get_form_by_id(form_id) if form_id else None
            return DistributionSummaryResponse(
                distribution_id=distribution_id,
                form_id=form_id or (form.id if form else UUID("00000000-0000-0000-0000-000000000000")),
                form_name=form.name if form else "Forms",
                version_number=form.current_version_number if form else 1,
                total_recipients=0,
                counts={"APPROVED": 0, "UNDER_REVIEW": 0, "RETURNED": 0, "RESUBMITTED": 0, "SUBMITTED": 0, "IN_PROGRESS": 0, "ASSIGNED": 0},
                recipients=[],
            )

        form_name = responses[0].form.name if responses[0].form else "Form"
        ver_num = responses[0].form_version.version_number if responses[0].form_version else 1

        counts: Dict[str, int] = {
            "APPROVED": 0,
            "UNDER_REVIEW": 0,
            "RETURNED": 0,
            "RESUBMITTED": 0,
            "SUBMITTED": 0,
            "IN_PROGRESS": 0,
            "ASSIGNED": 0,
        }

        recipient_items: List[RecipientSummaryItem] = []
        for r in responses:
            st = r.status.value if hasattr(r.status, "value") else str(r.status)
            counts[st] = counts.get(st, 0) + 1

            chk_items = r.checklist_items or []
            completed_chk = sum(1 for c in chk_items if c.status in [ChecklistStatus.PASSED, ChecklistStatus.WAIVED])

            recipient_items.append(
                RecipientSummaryItem(
                    response_id=r.id,
                    recipient_id=r.recipient_id,
                    recipient_name=r.recipient.profile.full_name if (r.recipient and hasattr(r.recipient, "profile") and r.recipient.profile) else (r.recipient.username if r.recipient else "Unknown"),
                    recipient_username=r.recipient.username if r.recipient else "unknown",
                    event_id=r.event_id,
                    event_name=r.event.name if r.event else None,
                    status=r.status,
                    submitted_at=r.submitted_at,
                    resubmitted_at=r.resubmitted_at,
                    current_phase=r.current_phase,
                    checklist_completed_count=completed_chk,
                    checklist_total_count=len(chk_items),
                )
            )

        return DistributionSummaryResponse(
            distribution_id=distribution_id,
            form_id=responses[0].form_id,
            form_name=form_name,
            version_number=ver_num,
            total_recipients=len(responses),
            counts=counts,
            recipients=recipient_items,
        )

    # -------------------------------------------------------------
    # 4. RESPONSE LIFECYCLE: SAVE DRAFT, SUBMIT & RESUBMIT
    # -------------------------------------------------------------

    def validate_submission_data(self, schema_fields: List[Dict[str, Any]], data: Dict[str, Any]):
        """Strict server-side validation against authoritative form schema."""
        for field in schema_fields:
            key = field.get("key")
            label = field.get("label", key)
            f_type = field.get("type", "TEXT")
            required = field.get("required", False)
            rules = field.get("validation_rules") or {}
            options = field.get("options") or []

            val = data.get(key)

            if required and (val is None or val == "" or (isinstance(val, list) and len(val) == 0)):
                raise ValidationException(f"Required field '{label}' ({key}) is missing or empty")

            if val is not None and val != "":
                if f_type == "NUMBER":
                    if not isinstance(val, (int, float)):
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            raise ValidationException(f"Field '{label}' must be a valid number")
                    min_v = rules.get("min_value")
                    max_v = rules.get("max_value")
                    if min_v is not None and val < min_v:
                        raise ValidationException(f"Field '{label}' must be at least {min_v}")
                    if max_v is not None and val > max_v:
                        raise ValidationException(f"Field '{label}' cannot exceed {max_v}")

                elif f_type in ["BOOLEAN", "YES_NO", "CHECKBOX"]:
                    if not isinstance(val, bool):
                        if str(val).lower() in ["true", "1", "yes"]:
                            data[key] = True
                        elif str(val).lower() in ["false", "0", "no"]:
                            data[key] = False

                elif f_type in ["TEXT", "LONG_TEXT"]:
                    val_str = str(val)
                    min_l = rules.get("min_length")
                    max_l = rules.get("max_length")
                    if min_l is not None and len(val_str) < min_l:
                        raise ValidationException(f"Field '{label}' must be at least {min_l} characters")
                    if max_l is not None and len(val_str) > max_l:
                        raise ValidationException(f"Field '{label}' cannot exceed {max_l} characters")

                elif f_type == "EMAIL":
                    val_str = str(val)
                    if "@" not in val_str or "." not in val_str:
                        raise ValidationException(f"Field '{label}' must be a valid email address")

                elif f_type in ["URL", "REFERENCE_LINK"]:
                    val_str = str(val).strip()
                    if not (val_str.startswith("http://") or val_str.startswith("https://")):
                        raise ValidationException(f"Field '{label}' must be a valid URL starting with http:// or https://")

                elif f_type in ["SELECT", "RADIO"]:
                    if options and str(val) not in options:
                        raise ValidationException(f"Field '{label}' value '{val}' is not in allowed options: {options}")

                elif f_type == "MULTI_SELECT":
                    if not isinstance(val, list):
                        raise ValidationException(f"Field '{label}' must be a list of selected options")
                    if options:
                        for item in val:
                            if str(item) not in options:
                                raise ValidationException(f"Option '{item}' for '{label}' is not in allowed options")

    def save_draft_response(self, response_id: UUID, data: FormResponseSaveDraft, user_id: UUID) -> FormResponse:
        """Persists draft responses to PostgreSQL safely."""
        resp = self.get_response_by_id(response_id)
        if resp.recipient_id != user_id:
            raise ForbiddenException("You can only edit your own assigned response instance.")

        if resp.status in [FormResponseStatus.APPROVED, FormResponseStatus.CANCELLED]:
            raise ValidationException(f"Cannot edit response in status '{resp.status.value}'")

        old_status = resp.status.value
        raw_data = data.response_data if data.response_data is not None else (data.submission_data or {})
        resp.response_data = raw_data
        if resp.status == FormResponseStatus.ASSIGNED:
            resp.status = FormResponseStatus.IN_PROGRESS

        history = FormWorkflowHistory(
            response_id=resp.id,
            actor_id=user_id,
            action="SAVED_DRAFT",
            from_status=old_status,
            to_status=resp.status.value,
            message="Draft answers saved to database.",
        )
        self.db.add(history)
        if hasattr(resp, "workflow_history") and resp.workflow_history is not None:
            resp.workflow_history.append(history)
        self.db.flush()
        return resp


    def submit_response(
        self,
        response_id: UUID,
        data: FormResponseSubmit,
        user_id: Optional[UUID] = None,
        submitter_id: Optional[UUID] = None,
    ) -> FormResponse:
        """Validates and transitions response from ASSIGNED/IN_PROGRESS/RETURNED to SUBMITTED or RESUBMITTED."""
        effective_user_id = user_id or submitter_id
        if not effective_user_id:
            raise ValidationException("Submitter/User ID must be provided to submit response.")
        user_id = effective_user_id
        resp = self.get_response_by_id(response_id)

        if resp.recipient_id != user_id:
            raise ForbiddenException("You can only submit your own assigned response.")

        version = self.db.get(FormVersion, resp.form_version_id)
        if not version:
            raise EntityNotFoundException("Form version associated with response not found.")

        raw_data = data.response_data if data.response_data is not None else (data.submission_data or {})
        self.validate_submission_data(version.schema, raw_data)

        resp.response_data = raw_data

        is_resubmission = resp.status == FormResponseStatus.RETURNED

        old_status = resp.status.value
        if is_resubmission:
            resp.status = FormResponseStatus.RESUBMITTED
            resp.resubmitted_at = datetime.now(timezone.utc)
            action_name = "RESUBMITTED"
            msg = f"Response resubmitted by @{resp.recipient.username if resp.recipient else 'submitter'} following return."
        else:
            resp.status = FormResponseStatus.SUBMITTED
            resp.submitted_at = datetime.now(timezone.utc)
            action_name = "SUBMITTED"
            msg = f"Response submitted by @{resp.recipient.username if resp.recipient else 'submitter'}."

        history = FormWorkflowHistory(
            response_id=resp.id,
            actor_id=user_id,
            action=action_name,
            from_status=old_status,
            to_status=resp.status.value,
            message=msg,
        )
        self.db.add(history)
        if hasattr(resp, "workflow_history") and resp.workflow_history is not None:
            resp.workflow_history.append(history)

        # Notify reviewer or distributor
        target_notify_id = resp.current_reviewer_id or (resp.distribution.distributor_id if resp.distribution else resp.form.owner_id)
        if target_notify_id and target_notify_id != user_id:
            self.notif_service.create_notification(
                recipient_id=target_notify_id,
                notification_type=NotificationType.FORM,
                title=f"Form Response {action_name}: {resp.form.name}",
                message=f"@{resp.recipient.username if resp.recipient else 'User'} has {action_name.lower()} response for '{resp.form.name}'.",
                related_resource_type="FORM_RESPONSE",
                related_resource_id=resp.id,
            )

        self.db.flush()
        return resp

    # -------------------------------------------------------------
    # 5. REVIEW WORKFLOW, CHECKLISTS & FORWARDING
    # -------------------------------------------------------------

    def review_response(
        self,
        response_id: UUID,
        data: FormResponseReviewRequest,
        reviewer_id: UUID,
        current_user: Optional[User] = None,
    ) -> FormResponse:
        """Review workflow handling approval and returns with mandatory reasons."""
        resp = self.get_response_by_id(response_id)
        if resp.recipient_id == reviewer_id:
            raise ForbiddenException("Self-review violation: Submitter cannot review their own response.")

        old_status = resp.status.value
        reviewer_name = current_user.username if current_user else "Reviewer"

        if data.action.upper() == "RETURN":
            if not data.return_reason or len(data.return_reason.strip()) < 3:
                raise ValidationException("A clear return reason is required when returning a response.")

            resp.status = FormResponseStatus.RETURNED
            resp.return_reason = data.return_reason.strip()
            resp.reviewer_remarks = data.reviewer_remarks
            resp.reviewed_at = datetime.now(timezone.utc)

            history = FormWorkflowHistory(
                response_id=resp.id,
                actor_id=reviewer_id,
                action="RETURNED",
                from_status=old_status,
                to_status=FormResponseStatus.RETURNED.value,
                message=f"Returned by @{reviewer_name}. Reason: {data.return_reason}",
                history_metadata={"reason": data.return_reason, "remarks": data.reviewer_remarks},
            )
            self.db.add(history)
            if hasattr(resp, "workflow_history") and resp.workflow_history is not None:
                resp.workflow_history.append(history)

            # Notify submitter
            if resp.recipient_id and resp.recipient_id != reviewer_id:
                self.notif_service.create_notification(
                    recipient_id=resp.recipient_id,
                    notification_type=NotificationType.FORM,
                    title=f"Form Response Returned: {resp.form.name}",
                    message=f"Your submission for '{resp.form.name}' was returned. Reason: {data.return_reason}",
                    related_resource_type="FORM_RESPONSE",
                    related_resource_id=resp.id,
                )

        elif data.action.upper() == "APPROVE":
            resp.status = FormResponseStatus.APPROVED
            resp.approved_at = datetime.now(timezone.utc)
            resp.reviewed_at = datetime.now(timezone.utc)
            resp.reviewer_remarks = data.reviewer_remarks

            history = FormWorkflowHistory(
                response_id=resp.id,
                actor_id=reviewer_id,
                action="APPROVED",
                from_status=old_status,
                to_status=FormResponseStatus.APPROVED.value,
                message=f"Approved by @{reviewer_name}. Remarks: {data.reviewer_remarks or 'None'}",
            )
            self.db.add(history)
            if hasattr(resp, "workflow_history") and resp.workflow_history is not None:
                resp.workflow_history.append(history)

            # Optional structured transformation
            if data.execute_transformation and resp.form_version.transformation_config:
                self._execute_transformation(resp, reviewer_id)

            # Notify submitter
            if resp.recipient_id and resp.recipient_id != reviewer_id:
                self.notif_service.create_notification(
                    recipient_id=resp.recipient_id,
                    notification_type=NotificationType.FORM,
                    title=f"Form Response Approved: {resp.form.name}",
                    message=f"Your submission for '{resp.form.name}' has been approved by @{reviewer_name}.",
                    related_resource_type="FORM_RESPONSE",
                    related_resource_id=resp.id,
                )

        else:
            raise ValidationException(f"Unknown review action '{data.action}'. Expected 'APPROVE' or 'RETURN'.")

        self.db.flush()
        return resp

    def _execute_transformation(self, resp: FormResponse, actor_id: UUID):
        """Transactional execution of transformation rules on approval."""
        cfg = resp.form_version.transformation_config
        if not cfg:
            return

        target_entity = cfg.get("target_entity", "TASK").upper()
        mappings = cfg.get("field_mappings", {})

        if target_entity == "TASK":
            title_field = mappings.get("title", "title")
            desc_field = mappings.get("description", "description")

            title_val = resp.response_data.get(title_field, f"Task from Form: {resp.form.name}")
            desc_val = resp.response_data.get(desc_field, f"Generated from response ID: {resp.id}")

            target_vert_id = resp.form.vertical_id
            if not target_vert_id:
                user_vert = self.db.scalar(select(UserVertical.vertical_id).where(UserVertical.user_id == resp.recipient_id).limit(1))
                if not user_vert:
                    target_vert_id = self.db.scalar(select(Vertical.id).limit(1))
                else:
                    target_vert_id = user_vert

            task = Task(
                title=str(title_val)[:255],
                description=str(desc_val),
                task_type=TaskType.ROUTINE,
                status=TaskStatus.NOT_STARTED,
                priority=TaskPriority.MEDIUM,
                assigned_to_id=resp.recipient_id,
                assigned_by_id=actor_id,
                vertical_id=target_vert_id,
                event_id=resp.event_id,
            )
            self.db.add(task)
            self.db.flush()

            resp.transformed_entity_type = "TASK"
            resp.transformed_entity_id = task.id
            logger.info(f"Transformed response {resp.id} into Task {task.id}")



        elif target_entity == "EVENT":
            name_field = mappings.get("name", "name")
            desc_field = mappings.get("description", "description")

            name_val = resp.response_data.get(name_field, f"Event from Form: {resp.form.name}")
            desc_val = resp.response_data.get(desc_field, f"Generated from response ID: {resp.id}")

            event = Event(
                name=str(name_val)[:255],
                description=str(desc_val),
                event_type=EventType.WORKSHOP,
                status=EventStatus.PLANNING,
                planned_date=date.today(),
                vertical_id=resp.form.vertical_id,
                created_by_id=actor_id,
            )
            self.db.add(event)
            self.db.flush()

            resp.transformed_entity_type = "EVENT"
            resp.transformed_entity_id = event.id
            logger.info(f"Transformed response {resp.id} into Event {event.id}")


    def forward_response(
        self,
        response_id: UUID,
        data: FormResponseForwardRequest,
        sender_id: UUID,
        current_user: Optional[User] = None,
    ) -> FormResponse:
        """Forward response to another authorized reviewer/coordinator without losing history."""
        resp = self.get_response_by_id(response_id)
        target_user = self.db.get(User, data.target_user_id)
        if not target_user:
            raise EntityNotFoundException(f"Target user '{data.target_user_id}' not found.")

        # Create reviewer record
        reviewer_entry = FormReviewer(
            response_id=resp.id,
            user_id=target_user.id,
            role_label=data.role_label or "Reviewer",
            phase_number=data.phase_number or (resp.current_phase + 1),
            status="PENDING",
        )
        self.db.add(reviewer_entry)
        resp.current_reviewer_id = target_user.id
        if data.phase_number:
            resp.current_phase = data.phase_number

        sender_name = current_user.username if current_user else "Sender"
        history = FormWorkflowHistory(
            response_id=resp.id,
            actor_id=sender_id,
            action="FORWARDED",
            from_status=resp.status.value,
            to_status=resp.status.value,
            message=f"Forwarded by @{sender_name} to @{target_user.username} ({data.role_label}): {data.message}",
            history_metadata={"target_user_id": str(target_user.id), "role_label": data.role_label, "note": data.message},
        )
        self.db.add(history)
        if hasattr(resp, "workflow_history") and resp.workflow_history is not None:
            resp.workflow_history.append(history)

        if target_user.id != sender_id:
            self.notif_service.create_notification(
                recipient_id=target_user.id,
                notification_type=NotificationType.FORM,
                title=f"Form Response Forwarded to You: {resp.form.name}",
                message=f"@{sender_name} forwarded response #{str(resp.id)[:8]} for review. Note: {data.message}",
                related_resource_type="FORM_RESPONSE",
                related_resource_id=resp.id,
            )
        self.db.flush()
        return resp


    def update_checklist_item(
        self,
        item_id: UUID,
        data: ChecklistItemUpdate,
        user_id: UUID,
        current_user: Optional[User] = None,
    ) -> FormChecklistItem:
        item = self.db.get(FormChecklistItem, item_id)
        if not item:
            raise EntityNotFoundException(f"Checklist item '{item_id}' not found.")

        item.status = data.status
        if data.remarks is not None:
            item.remarks = data.remarks
        if data.evidence_link is not None:
            item.evidence_link = data.evidence_link
        item.reviewer_id = user_id
        item.completed_at = datetime.now(timezone.utc)

        user_name = current_user.username if current_user else "Reviewer"
        history = FormWorkflowHistory(
            response_id=item.response_id,
            actor_id=user_id,
            action="CHECKLIST_UPDATED",
            message=f"Checklist item '{item.title}' set to {data.status.value} by @{user_name}.",
            history_metadata={"item_id": str(item.id), "title": item.title, "status": data.status.value},
        )
        self.db.add(history)
        self.db.flush()
        return item

    # -------------------------------------------------------------
    # 6. SCOPED QUERIES & WORKSPACE VIEWS
    # -------------------------------------------------------------

    def get_response_by_id(self, response_id: UUID, current_user: Optional[User] = None) -> FormResponse:
        self.db.expire_all()
        resp = self.db.scalar(
            select(FormResponse)
            .where(FormResponse.id == response_id)
            .options(
                selectinload(FormResponse.form),
                selectinload(FormResponse.form_version),
                selectinload(FormResponse.distribution),
                selectinload(FormResponse.recipient),
                selectinload(FormResponse.event),
                selectinload(FormResponse.current_reviewer),
                selectinload(FormResponse.reviewers).selectinload(FormReviewer.user),
                selectinload(FormResponse.checklist_items).selectinload(FormChecklistItem.reviewer),
                selectinload(FormResponse.workflow_history).selectinload(FormWorkflowHistory.actor),
            )
        )
        if not resp:
            raise EntityNotFoundException(f"Form response with ID '{response_id}' not found")


        # Object-level authorization check
        if current_user:
            roles = self._get_user_roles(current_user)
            if "ADMIN" not in roles and "SPORTS_CORE" not in roles:
                user_id = current_user.id
                user_verts = self._get_user_vertical_ids(current_user)

                is_recipient = resp.recipient_id == user_id
                is_creator = resp.form.owner_id == user_id
                is_distributor = resp.distribution and resp.distribution.distributor_id == user_id
                is_reviewer = resp.current_reviewer_id == user_id or any(r.user_id == user_id for r in resp.reviewers)
                is_vertical_member = resp.form.vertical_id in user_verts if resp.form.vertical_id else False

                if not (is_recipient or is_creator or is_distributor or is_reviewer or is_vertical_member):
                    raise ForbiddenException("You do not have authorization to view this form response instance.")

        return resp

    def list_responses(
        self,
        form_id: Optional[UUID] = None,
        distribution_id: Optional[UUID] = None,
        recipient_id: Optional[UUID] = None,
        status: Optional[FormResponseStatus] = None,
        workspace_tab: Optional[str] = None,  # assigned_to_me, my_created, my_distributed, pending_review, returned, completed, shared_with_me, all
        current_user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[FormResponse], int]:
        stmt = select(FormResponse).options(
            selectinload(FormResponse.form),
            selectinload(FormResponse.form_version),
            selectinload(FormResponse.distribution),
            selectinload(FormResponse.recipient),
            selectinload(FormResponse.event),
            selectinload(FormResponse.current_reviewer),
            selectinload(FormResponse.reviewers).selectinload(FormReviewer.user),
            selectinload(FormResponse.checklist_items).selectinload(FormChecklistItem.reviewer),
            selectinload(FormResponse.workflow_history).selectinload(FormWorkflowHistory.actor),
        )
        count_stmt = select(func.count(FormResponse.id))

        if form_id:
            stmt = stmt.where(FormResponse.form_id == form_id)
            count_stmt = count_stmt.where(FormResponse.form_id == form_id)
        if distribution_id:
            stmt = stmt.where(FormResponse.distribution_id == distribution_id)
            count_stmt = count_stmt.where(FormResponse.distribution_id == distribution_id)
        if recipient_id:
            stmt = stmt.where(FormResponse.recipient_id == recipient_id)
            count_stmt = count_stmt.where(FormResponse.recipient_id == recipient_id)
        if status:
            stmt = stmt.where(FormResponse.status == status)
            count_stmt = count_stmt.where(FormResponse.status == status)

        # Tab-based filtering
        if current_user and workspace_tab:
            uid = current_user.id
            if workspace_tab == "assigned_to_me":
                stmt = stmt.where(FormResponse.recipient_id == uid, FormResponse.status.in_([FormResponseStatus.ASSIGNED, FormResponseStatus.IN_PROGRESS, FormResponseStatus.RETURNED]))
                count_stmt = count_stmt.where(FormResponse.recipient_id == uid, FormResponse.status.in_([FormResponseStatus.ASSIGNED, FormResponseStatus.IN_PROGRESS, FormResponseStatus.RETURNED]))
            elif workspace_tab == "my_created":
                stmt = stmt.join(Form, Form.id == FormResponse.form_id).where(Form.owner_id == uid)
                count_stmt = count_stmt.join(Form, Form.id == FormResponse.form_id).where(Form.owner_id == uid)
            elif workspace_tab == "my_distributed":
                stmt = stmt.join(FormDistribution, FormDistribution.id == FormResponse.distribution_id).where(FormDistribution.distributor_id == uid)
                count_stmt = count_stmt.join(FormDistribution, FormDistribution.id == FormResponse.distribution_id).where(FormDistribution.distributor_id == uid)
            elif workspace_tab == "pending_review":
                # Only submissions where user is the assigned reviewer and NOT the submitter
                reviewer_cond = or_(
                    FormResponse.current_reviewer_id == uid,
                    FormResponse.reviewers.any(FormReviewer.user_id == uid),
                )
                stmt = stmt.where(
                    reviewer_cond,
                    FormResponse.status.in_([FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED, FormResponseStatus.UNDER_REVIEW]),
                    FormResponse.recipient_id != uid,
                )
                count_stmt = count_stmt.where(
                    reviewer_cond,
                    FormResponse.status.in_([FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED, FormResponseStatus.UNDER_REVIEW]),
                    FormResponse.recipient_id != uid,
                )
            elif workspace_tab == "returned":
                stmt = stmt.where(FormResponse.recipient_id == uid, FormResponse.status == FormResponseStatus.RETURNED)
                count_stmt = count_stmt.where(FormResponse.recipient_id == uid, FormResponse.status == FormResponseStatus.RETURNED)
            elif workspace_tab == "completed":
                stmt = stmt.where(FormResponse.recipient_id == uid, FormResponse.status.in_([FormResponseStatus.APPROVED, FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED]))
                count_stmt = count_stmt.where(FormResponse.recipient_id == uid, FormResponse.status.in_([FormResponseStatus.APPROVED, FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED]))
            elif workspace_tab == "shared_with_me":
                stmt = stmt.join(FormReviewer, FormReviewer.response_id == FormResponse.id).where(FormReviewer.user_id == uid, FormResponse.recipient_id != uid)
                count_stmt = count_stmt.join(FormReviewer, FormReviewer.response_id == FormResponse.id).where(FormReviewer.user_id == uid, FormResponse.recipient_id != uid)

        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(stmt.order_by(FormResponse.created_at.desc()).offset(offset).limit(limit)).all())
        return items, total

    def get_dashboard_stats(self, current_user: Optional[User] = None) -> FormDashboardStats:
        """Rollup metrics strictly scoped to the authenticated user."""
        if current_user:
            uid = current_user.id
            total_forms = self.db.scalar(select(func.count(Form.id)).where(Form.owner_id == uid)) or 0
            published_forms = self.db.scalar(select(func.count(Form.id)).where(Form.owner_id == uid, Form.status == FormStatus.PUBLISHED)) or 0
            total_dist = self.db.scalar(select(func.count(FormDistribution.id)).where(FormDistribution.distributor_id == uid)) or 0
            total_resp = self.db.scalar(select(func.count(FormResponse.id)).where(FormResponse.recipient_id == uid)) or 0

            reviewer_cond = or_(
                FormResponse.current_reviewer_id == uid,
                FormResponse.reviewers.any(FormReviewer.user_id == uid),
            )
            pending_rev = self.db.scalar(
                select(func.count(FormResponse.id)).where(
                    reviewer_cond,
                    FormResponse.status.in_([FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED, FormResponseStatus.UNDER_REVIEW]),
                    FormResponse.recipient_id != uid,
                )
            ) or 0
            returned_resp = self.db.scalar(
                select(func.count(FormResponse.id)).where(
                    FormResponse.recipient_id == uid,
                    FormResponse.status == FormResponseStatus.RETURNED,
                )
            ) or 0
            approved_resp = self.db.scalar(
                select(func.count(FormResponse.id)).where(
                    FormResponse.recipient_id == uid,
                    FormResponse.status == FormResponseStatus.APPROVED,
                )
            ) or 0
        else:
            total_forms = self.db.scalar(select(func.count(Form.id))) or 0
            published_forms = self.db.scalar(select(func.count(Form.id)).where(Form.status == FormStatus.PUBLISHED)) or 0
            total_dist = self.db.scalar(select(func.count(FormDistribution.id))) or 0
            total_resp = self.db.scalar(select(func.count(FormResponse.id))) or 0
            pending_rev = self.db.scalar(select(func.count(FormResponse.id)).where(FormResponse.status.in_([FormResponseStatus.SUBMITTED, FormResponseStatus.RESUBMITTED, FormResponseStatus.UNDER_REVIEW]))) or 0
            returned_resp = self.db.scalar(select(func.count(FormResponse.id)).where(FormResponse.status == FormResponseStatus.RETURNED)) or 0
            approved_resp = self.db.scalar(select(func.count(FormResponse.id)).where(FormResponse.status == FormResponseStatus.APPROVED)) or 0

        return FormDashboardStats(
            total_forms=total_forms,
            published_forms=published_forms,
            total_distributions=total_dist,
            total_responses=total_resp,
            pending_review=pending_rev,
            returned_responses=returned_resp,
            approved_responses=approved_resp,
        )


    # -------------------------------------------------------------
    # 7. BACKWARD COMPATIBILITY HELPERS
    # -------------------------------------------------------------

    def submit_form(self, form_id: UUID, data: Any, submitter_id: UUID, current_user: Optional[User] = None) -> FormResponse:
        """Legacy single-call helper: finds/creates response instance and submits it."""
        form = self.get_form_by_id(form_id)

        # Audience check
        if current_user:
            roles = self._get_user_roles(current_user)
            if form.target_audience == FormAudience.ORGANIZATION and roles == ["EVENT_TEAM"]:
                raise ForbiddenException("Event teams do not have permission to submit to internal organization forms.")

        version = self.get_latest_published_version(form_id)


        resp = self.db.scalar(
            select(FormResponse).where(
                FormResponse.form_id == form_id,
                FormResponse.recipient_id == submitter_id,
                FormResponse.status.in_([FormResponseStatus.ASSIGNED, FormResponseStatus.IN_PROGRESS, FormResponseStatus.RETURNED]),
            )
        )
        if not resp:
            resp = FormResponse(
                form_id=form.id,
                form_version_id=version.id,
                recipient_id=submitter_id,
                status=FormResponseStatus.ASSIGNED,
                response_data={},
            )
            self.db.add(resp)
            self.db.flush()

        raw_data = getattr(data, "submission_data", None) or getattr(data, "response_data", None) or (data if isinstance(data, dict) else {})
        submit_req = FormResponseSubmit(response_data=raw_data)
        return self.submit_response(resp.id, submit_req, user_id=submitter_id)


    def review_submission(
        self,
        submission_id: UUID,
        arg2: Any = None,
        arg3: Any = None,
        data: Any = None,
        reviewer_id: Optional[UUID] = None,
        current_user: Optional[User] = None,
        **kwargs,
    ) -> FormResponse:
        """Legacy submission review helper handling both positional and keyword argument styles."""
        actual_data = data or kwargs.get("review_data")
        actual_reviewer_id = reviewer_id or kwargs.get("actor_id")

        if actual_data is None:
            if isinstance(arg2, (UUID, str)) and (isinstance(arg3, (dict, BaseModel)) or hasattr(arg3, "status") or hasattr(arg3, "action")):
                actual_reviewer_id = UUID(str(arg2)) if isinstance(arg2, str) else arg2
                actual_data = arg3
            elif isinstance(arg3, (UUID, str)):
                actual_reviewer_id = UUID(str(arg3)) if isinstance(arg3, str) else arg3
                actual_data = arg2
            else:
                actual_data = arg2
                if actual_reviewer_id is None and arg3:
                    actual_reviewer_id = UUID(str(arg3)) if isinstance(arg3, str) else arg3
        else:
            if actual_reviewer_id is None and isinstance(arg2, (UUID, str)):
                actual_reviewer_id = UUID(str(arg2)) if isinstance(arg2, str) else arg2

        action = getattr(actual_data, "action", None)
        if hasattr(action, "value"):
            action = action.value
        elif action is None:
            decision = getattr(actual_data, "decision", None) or getattr(actual_data, "status", None)
            if hasattr(decision, "value"):
                decision = decision.value
            action = "APPROVE" if any(x in str(decision).upper() for x in ["APPROV", "ACCEPT"]) else "RETURN"

        review_req = FormResponseReviewRequest(
            action=str(action).upper(),
            return_reason=getattr(actual_data, "return_reason", None) or getattr(actual_data, "review_comments", None) or "Returned for review corrections",
            reviewer_remarks=getattr(actual_data, "reviewer_remarks", None) or getattr(actual_data, "review_comments", None),
            execute_transformation=getattr(actual_data, "execute_transformation", True),
        )
        return self.review_response(submission_id, review_req, reviewer_id=actual_reviewer_id, current_user=current_user)



    def list_submissions(self, **kwargs) -> Tuple[List[FormResponse], int]:
        return self.list_responses(**kwargs)

    def get_submission_by_id(self, submission_id: UUID, current_user: Optional[User] = None) -> FormResponse:
        return self.get_response_by_id(submission_id, current_user=current_user)
