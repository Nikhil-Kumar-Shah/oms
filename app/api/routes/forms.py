"""
Advanced Forms, Distributions, Responses & Multi-Phase Review Workflow API Endpoints
Paradox Sports OMS - Phase 11 Form & Response Workflow System
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.form import FormResponseStatus, FormStatus
from app.models.user import User
from app.schemas.form import (
    ChecklistItemUpdate,
    DistributionSummaryResponse,
    FormChecklistItemResponse,
    FormCreate,
    FormDashboardStats,
    FormDistributeRequest,
    FormDistributionResponse,
    FormListResponse,
    FormResponseDetailsResponse,
    FormResponseForwardRequest,
    FormResponseListResponse,
    FormResponseModel,
    FormResponseReturnRequest,
    FormResponseReviewRequest,
    FormResponseSaveDraft,
    FormResponseSubmit,
    FormReviewerResponse,
    FormUpdate,
    FormVersionCreate,
    FormVersionResponse,
    FormWorkflowHistoryResponse,
)
from app.services.form_service import FormService

router = APIRouter(tags=["Advanced Forms & Workflow"])


def _format_version_response(v) -> FormVersionResponse:
    return FormVersionResponse(
        id=v.id,
        form_id=v.form_id,
        version_number=v.version_number,
        sections=v.sections or [],
        schema_fields=v.schema or [],
        review_config=v.review_config,
        transformation_config=v.transformation_config,
        is_published=v.is_published,
        published_at=v.published_at,
        published_by_id=v.published_by_id,
        published_by_username=v.published_by.username if getattr(v, "published_by", None) else None,
        created_at=v.created_at,
    )


def _format_form_response(f) -> FormResponseModel:
    latest_v = None
    if f.versions:
        published = [v for v in f.versions if v.is_published]
        target_v = published[-1] if published else f.versions[-1]
        latest_v = _format_version_response(target_v)

    dists = []
    if getattr(f, "distributions", None):
        for d in f.distributions:
            dists.append(
                FormDistributionResponse(
                    id=d.id,
                    form_id=d.form_id,
                    form_name=f.name,
                    form_version_id=d.form_version_id,
                    distributor_id=d.distributor_id,
                    distributor_username=d.distributor.username if getattr(d, "distributor", None) else None,
                    title=d.title,
                    instructions=d.instructions,
                    deadline=d.deadline,
                    recipient_count=d.recipient_count,
                    created_at=d.created_at,
                )
            )

    resps = f.responses if getattr(f, "responses", None) else []
    total_recips = len(resps)
    if total_recips == 0 and dists:
        total_recips = dists[0].recipient_count or 0
    elif total_recips == 0 and f.distribution_config and f.distribution_config.get("recipient_ids"):
        total_recips = len(f.distribution_config.get("recipient_ids") or [])

    not_started_cnt = 0
    pending_cnt = 0
    completed_cnt = 0
    received_cnt = 0

    for r in resps:
        st = r.status.value if hasattr(r.status, "value") else str(r.status)
        if st == "ASSIGNED":
            not_started_cnt += 1
        elif st in ["IN_PROGRESS", "RETURNED", "UNDER_REVIEW"]:
            pending_cnt += 1
            if st in ["RETURNED", "UNDER_REVIEW"]:
                received_cnt += 1
        elif st in ["APPROVED", "SUBMITTED", "RESUBMITTED"]:
            completed_cnt += 1
            received_cnt += 1

    completion_pct = round((completed_cnt / total_recips) * 100, 1) if total_recips > 0 else 0.0

    deadline = None
    if dists and dists[0].deadline:
        deadline = dists[0].deadline
    elif f.distribution_config and f.distribution_config.get("deadline"):
        try:
            deadline = datetime.fromisoformat(str(f.distribution_config["deadline"]))
        except Exception:
            pass

    return FormResponseModel(
        id=f.id,
        name=f.name,
        description=f.description,
        purpose=f.purpose,
        instructions=f.instructions,
        category=f.category,
        status=f.status,
        owner_id=f.owner_id,
        owner_username=f.owner.username if f.owner else None,
        vertical_id=f.vertical_id,
        vertical_name=f.vertical.name if f.vertical else None,
        event_id=f.event_id,
        event_name=f.event.name if getattr(f, "event", None) else None,
        target_audience=f.target_audience,
        current_version_number=f.current_version_number,
        distribution_config=f.distribution_config or {},
        created_at=f.created_at,
        updated_at=f.updated_at,
        latest_version=latest_v,
        distributions=dists,
        total_recipients=total_recips,
        responses_received=received_cnt,
        pending_responses=pending_cnt,
        not_started_responses=not_started_cnt,
        completed_responses=completed_cnt,
        completion_percentage=completion_pct,
        deadline=deadline,
    )


def _format_response_details(r) -> FormResponseDetailsResponse:
    version = r.form_version
    sections = version.sections if version and version.sections else []
    schema_fields = version.schema if version and version.schema else []

    reviewers_list = []
    if r.reviewers:
        for rev in r.reviewers:
            reviewers_list.append(
                FormReviewerResponse(
                    id=rev.id,
                    response_id=rev.response_id,
                    user_id=rev.user_id,
                    username=rev.user.username if rev.user else None,
                    full_name=rev.user.profile.full_name if (rev.user and hasattr(rev.user, "profile") and rev.user.profile) else None,
                    role_label=rev.role_label,
                    phase_number=rev.phase_number,
                    status=rev.status,
                    decision_comments=rev.decision_comments,
                    decided_at=rev.decided_at,
                    created_at=rev.created_at,
                )
            )

    checklist_list = []
    if r.checklist_items:
        for chk in r.checklist_items:
            checklist_list.append(
                FormChecklistItemResponse(
                    id=chk.id,
                    response_id=chk.response_id,
                    phase_number=chk.phase_number,
                    phase_name=chk.phase_name,
                    title=chk.title,
                    description=chk.description,
                    reviewer_id=chk.reviewer_id,
                    reviewer_username=chk.reviewer.username if chk.reviewer else None,
                    reviewer_name=chk.reviewer.profile.full_name if (chk.reviewer and hasattr(chk.reviewer, "profile") and chk.reviewer.profile) else None,
                    status=chk.status,
                    remarks=chk.remarks,
                    evidence_link=chk.evidence_link,
                    completed_at=chk.completed_at,
                    created_at=chk.created_at,
                )
            )

    history_list = []
    if r.workflow_history:
        for h in r.workflow_history:
            history_list.append(
                FormWorkflowHistoryResponse(
                    id=h.id,
                    response_id=h.response_id,
                    actor_id=h.actor_id,
                    actor_username=h.actor.username if h.actor else None,
                    actor_full_name=h.actor.profile.full_name if (h.actor and hasattr(h.actor, "profile") and h.actor.profile) else None,
                    action=h.action,
                    from_status=h.from_status,
                    to_status=h.to_status,
                    message=h.message,
                    history_metadata=h.history_metadata,
                    created_at=h.created_at,
                )
            )

    return FormResponseDetailsResponse(
        id=r.id,
        form_id=r.form_id,
        form_name=r.form.name if r.form else None,
        form_description=r.form.description if r.form else None,
        form_purpose=r.form.purpose if r.form else None,
        form_instructions=r.form.instructions if r.form else None,
        form_version_id=r.form_version_id,
        version_number=r.form_version.version_number if r.form_version else None,
        distribution_id=r.distribution_id,
        recipient_id=r.recipient_id,
        recipient_username=r.recipient.username if r.recipient else None,
        recipient_name=r.recipient.profile.full_name if (r.recipient and hasattr(r.recipient, "profile") and r.recipient.profile) else None,
        event_id=r.event_id,
        event_name=r.event.name if r.event else None,
        status=r.status,
        response_data=r.response_data or {},
        submitted_at=r.submitted_at,
        resubmitted_at=r.resubmitted_at,
        reviewed_at=r.reviewed_at,
        approved_at=r.approved_at,
        deadline=r.deadline,
        return_reason=r.return_reason,
        reviewer_remarks=r.reviewer_remarks,
        current_reviewer_id=r.current_reviewer_id,
        current_reviewer_username=r.current_reviewer.username if r.current_reviewer else None,
        current_phase=r.current_phase,
        sections=sections,
        schema_fields=schema_fields,
        reviewers=reviewers_list,
        checklist_items=checklist_list,
        workflow_history=history_list,
        transformed_entity_type=r.transformed_entity_type,
        transformed_entity_id=r.transformed_entity_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )



# -------------------------------------------------------------
# 1. TEMPLATES & VERSIONS
# -------------------------------------------------------------

@router.get("/forms/dashboard-stats", response_model=FormDashboardStats)
def get_forms_dashboard_stats(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    return service.get_dashboard_stats(current_user=current_user)


@router.get("/forms", response_model=FormListResponse)
def list_forms(
    vertical_id: Optional[UUID] = Query(None),
    event_id: Optional[UUID] = Query(None),
    status: Optional[FormStatus] = Query(None),
    category: Optional[str] = Query(None),
    workspace_tab: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    forms, total = service.list_forms(
        vertical_id=vertical_id,
        event_id=event_id,
        status=status,
        category=category,
        workspace_tab=workspace_tab,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    items = [_format_form_response(f) for f in forms]
    return FormListResponse(total=total, items=items)



@router.post("/forms", response_model=FormResponseModel, status_code=status.HTTP_201_CREATED)
def create_form(
    data: FormCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    form = service.create_form(data, owner_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_form_response(service.get_form_by_id(form.id))


@router.get("/forms/{form_id}", response_model=FormResponseModel)
def get_form(
    form_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    return _format_form_response(service.get_form_by_id(form_id, current_user=current_user))


@router.patch("/forms/{form_id}", response_model=FormResponseModel)
def update_form(
    form_id: UUID,
    data: FormUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    form = service.update_form(form_id, data, actor_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_form_response(service.get_form_by_id(form.id))


@router.post("/forms/{form_id}/versions", response_model=FormVersionResponse, status_code=status.HTTP_201_CREATED)
def create_form_version(
    form_id: UUID,
    data: FormVersionCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    version = service.create_form_version(form_id, data, actor_id=current_user.id)
    db.commit()
    return _format_version_response(version)


@router.post("/forms/{form_id}/publish", response_model=FormVersionResponse)
def publish_form_version(
    form_id: UUID,
    version_number: int = Query(..., ge=1),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    version = service.publish_form_version(form_id, version_number, actor_id=current_user.id)
    db.commit()
    return _format_version_response(version)


# -------------------------------------------------------------
# 2. DISTRIBUTION & TRACKING
# -------------------------------------------------------------

@router.post("/forms/{form_id}/distribute", response_model=FormDistributionResponse, status_code=status.HTTP_201_CREATED)
def distribute_form(
    form_id: UUID,
    data: FormDistributeRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    dist = service.distribute_form(form_id, data, distributor_id=current_user.id, current_user=current_user)
    db.commit()
    return FormDistributionResponse(
        id=dist.id,
        form_id=dist.form_id,
        form_name=dist.form.name if dist.form else None,
        form_version_id=dist.form_version_id,
        distributor_id=dist.distributor_id,
        distributor_username=current_user.username,
        title=dist.title,
        instructions=dist.instructions,
        deadline=dist.deadline,
        recipient_count=dist.recipient_count,
        created_at=dist.created_at,
    )


@router.get("/forms/{form_id}/distribution-summary", response_model=DistributionSummaryResponse)
def get_form_distribution_summary(
    form_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    return service.get_distribution_summary(form_id=form_id)


# -------------------------------------------------------------
# 3. RESPONSE INSTANCES & WORKFLOWS
# -------------------------------------------------------------

@router.get("/form-responses", response_model=FormResponseListResponse)
@router.get("/form-submissions", response_model=FormResponseListResponse)
def list_form_responses(
    form_id: Optional[UUID] = Query(None),
    distribution_id: Optional[UUID] = Query(None),
    recipient_id: Optional[UUID] = Query(None),
    submitter_id: Optional[UUID] = Query(None),
    status: Optional[FormResponseStatus] = Query(None),
    workspace_tab: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    target_recip = recipient_id or submitter_id
    responses, total = service.list_responses(
        form_id=form_id,
        distribution_id=distribution_id,
        recipient_id=target_recip,
        status=status,
        workspace_tab=workspace_tab,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    items = [_format_response_details(r) for r in responses]
    return FormResponseListResponse(total=total, items=items)


@router.get("/form-responses/{response_id}", response_model=FormResponseDetailsResponse)
@router.get("/form-submissions/{response_id}", response_model=FormResponseDetailsResponse)
def get_form_response(
    response_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.get_response_by_id(response_id, current_user=current_user)
    return _format_response_details(resp)


@router.post("/form-responses/{response_id}/draft", response_model=FormResponseDetailsResponse)
def save_draft_response(
    response_id: UUID,
    data: FormResponseSaveDraft,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.save_draft_response(response_id, data, user_id=current_user.id)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))


@router.post("/forms/{form_id}/submissions", response_model=FormResponseDetailsResponse, status_code=status.HTTP_201_CREATED)
def submit_form_legacy(
    form_id: UUID,
    data: FormResponseSubmit,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.submit_form(form_id, data, submitter_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))


@router.post("/form-responses/{response_id}/submit", response_model=FormResponseDetailsResponse)
def submit_response(
    response_id: UUID,
    data: FormResponseSubmit,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.submit_response(response_id, data, user_id=current_user.id)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))



@router.post("/form-responses/{response_id}/review", response_model=FormResponseDetailsResponse)
@router.post("/form-submissions/{response_id}/review", response_model=FormResponseDetailsResponse)
def review_response(
    response_id: UUID,
    data: FormResponseReviewRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.review_response(response_id, data, reviewer_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))


@router.post("/form-responses/{response_id}/return", response_model=FormResponseDetailsResponse)
def return_response(
    response_id: UUID,
    data: FormResponseReturnRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    review_req = FormResponseReviewRequest(
        action="RETURN",
        return_reason=data.return_reason,
        reviewer_remarks=data.reviewer_remarks,
    )
    resp = service.review_response(response_id, review_req, reviewer_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))


@router.post("/form-responses/{response_id}/forward", response_model=FormResponseDetailsResponse)
def forward_response(
    response_id: UUID,
    data: FormResponseForwardRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = FormService(db)
    resp = service.forward_response(response_id, data, sender_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_response_details(service.get_response_by_id(resp.id))


@router.patch("/form-responses/checklist/{item_id}", response_model=FormChecklistItemResponse)
def update_checklist_item(
    item_id: UUID,
    data: ChecklistItemUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):

    service = FormService(db)
    item = service.update_checklist_item(item_id, data, user_id=current_user.id, current_user=current_user)
    db.commit()
    return FormChecklistItemResponse(
        id=item.id,
        response_id=item.response_id,
        phase_number=item.phase_number,
        phase_name=item.phase_name,
        title=item.title,
        description=item.description,
        reviewer_id=item.reviewer_id,
        reviewer_username=current_user.username,
        reviewer_name=current_user.profile.full_name if (hasattr(current_user, "profile") and current_user.profile) else current_user.username,
        status=item.status,
        remarks=item.remarks,
        evidence_link=item.evidence_link,
        completed_at=item.completed_at,
        created_at=item.created_at,
    )
