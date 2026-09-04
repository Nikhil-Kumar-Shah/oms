"""
Advanced Forms, Form Versions, Distributions, Responses, Checklists & Workflow History Schemas
Paradox Sports OMS - Phase 11 Form & Response Workflow System
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.form import ChecklistStatus, FormAudience, FormFieldType, FormResponseStatus, FormStatus



class FormFieldSchema(BaseModel):
    id: Optional[str] = None
    key: str = Field(..., min_length=1, max_length=64, example="rulebook_url")
    label: str = Field(..., min_length=1, max_length=255, example="Tournament Rulebook Reference URL")
    type: FormFieldType = FormFieldType.TEXT
    required: bool = True
    default_value: Optional[Any] = None
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None  # for SELECT / MULTI_SELECT / RADIO
    validation_rules: Optional[Dict[str, Any]] = None  # min_length, max_length, min_value, max_value, regex
    ordering: int = 0
    help_text: Optional[str] = None



class FormSectionSchema(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=255, example="Basic Event Information")
    description: Optional[str] = None
    ordering: int = 0
    fields: List[FormFieldSchema] = Field(default_factory=list)


class FormChecklistConfigItem(BaseModel):
    phase_number: int = 1
    phase_name: str = "POC Review"
    title: str = "Rulebook Reference Verified"
    description: Optional[str] = "Verify link points to authoritative Google Drive document"
    role_label: Optional[str] = "POC"


class FormTransformationConfig(BaseModel):
    target_entity: str = Field(..., example="TASK")  # "TASK", "REQUIREMENT", "EVENT"
    field_mappings: Dict[str, str] = Field(..., example={"title": "summary_field", "description": "details_field"})


class FormVersionCreate(BaseModel):
    sections: Optional[List[FormSectionSchema]] = None
    schema_fields: Optional[List[FormFieldSchema]] = None
    review_config: Optional[List[FormChecklistConfigItem]] = None
    transformation_config: Optional[FormTransformationConfig] = None


class FormVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    form_id: UUID
    version_number: int
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    schema_fields: List[Dict[str, Any]] = Field(default_factory=list, validation_alias="schema")
    review_config: Optional[List[Dict[str, Any]]] = None
    transformation_config: Optional[Dict[str, Any]] = None
    is_published: bool
    published_at: Optional[datetime] = None
    published_by_id: Optional[UUID] = None
    published_by_username: Optional[str] = None
    created_at: datetime


class FormBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, example="Event Rulebook Submission")
    description: Optional[str] = None
    purpose: str = Field(..., min_length=1, max_length=255, example="Standardized rulebook collection")
    instructions: Optional[str] = None
    category: Optional[str] = "Operational"
    target_audience: FormAudience = FormAudience.ORGANIZATION
    distribution_config: Optional[Dict[str, Any]] = None


class FormCreate(FormBase):
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    sections: Optional[List[FormSectionSchema]] = None
    initial_schema: Optional[List[FormFieldSchema]] = None
    review_config: Optional[List[FormChecklistConfigItem]] = None
    transformation_config: Optional[FormTransformationConfig] = None
    publish_and_distribute: Optional[bool] = False
    recipient_ids: Optional[List[UUID]] = None
    distribution_deadline: Optional[datetime] = None
    distribution_instructions: Optional[str] = None


class FormUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    purpose: Optional[str] = None
    instructions: Optional[str] = None
    category: Optional[str] = None
    target_audience: Optional[FormAudience] = None
    vertical_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    status: Optional[FormStatus] = None
    sections: Optional[List[FormSectionSchema]] = None
    distribution_config: Optional[Dict[str, Any]] = None
    publish_and_distribute: Optional[bool] = False
    recipient_ids: Optional[List[UUID]] = None
    distribution_deadline: Optional[datetime] = None
    distribution_instructions: Optional[str] = None


class FormResponseModel(FormBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: FormStatus
    owner_id: UUID
    owner_username: Optional[str] = None
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    current_version_number: int
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[FormVersionResponse] = None
    distributions: Optional[List['FormDistributionResponse']] = None
    total_recipients: int = 0
    responses_received: int = 0
    pending_responses: int = 0
    not_started_responses: int = 0
    completed_responses: int = 0
    completion_percentage: float = 0.0
    deadline: Optional[datetime] = None


# Backward compatibility alias
FormResponse = FormResponseModel


class FormListResponse(BaseModel):
    total: int
    items: List[FormResponseModel]


# -------------------------------------------------------------
# Distribution Schemas
# -------------------------------------------------------------

class FormReviewerAssignInput(BaseModel):
    user_id: UUID
    role_label: str = "Reviewer"
    phase_number: int = 1


class FormDistributeRequest(BaseModel):
    recipient_ids: List[UUID] = Field(..., min_length=1, example=["u1-uuid", "u2-uuid"])
    deadline: Optional[datetime] = None
    instructions: Optional[str] = None
    reviewers: Optional[List[FormReviewerAssignInput]] = None


class FormDistributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    form_name: Optional[str] = None
    form_version_id: UUID
    distributor_id: UUID
    distributor_username: Optional[str] = None
    title: Optional[str] = None
    instructions: Optional[str] = None
    deadline: Optional[datetime] = None
    recipient_count: int
    created_at: datetime


FormResponseModel.model_rebuild()


class RecipientSummaryItem(BaseModel):
    response_id: UUID
    recipient_id: UUID
    recipient_name: str
    recipient_username: str
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    status: FormResponseStatus
    submitted_at: Optional[datetime] = None
    resubmitted_at: Optional[datetime] = None
    current_phase: int = 1
    checklist_completed_count: int = 0
    checklist_total_count: int = 0


class DistributionSummaryResponse(BaseModel):
    distribution_id: Optional[UUID] = None
    form_id: UUID
    form_name: str
    version_number: int
    total_recipients: int
    counts: Dict[str, int]
    recipients: List[RecipientSummaryItem]


# -------------------------------------------------------------
# Response Instance & Workflow Schemas
# -------------------------------------------------------------

class FormReviewerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    user_id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_label: str
    phase_number: int
    status: str
    decision_comments: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime


class FormChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    phase_number: int
    phase_name: str
    title: str
    description: Optional[str] = None
    reviewer_id: Optional[UUID] = None
    reviewer_username: Optional[str] = None
    reviewer_name: Optional[str] = None
    status: ChecklistStatus
    remarks: Optional[str] = None
    evidence_link: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ChecklistItemUpdate(BaseModel):
    status: ChecklistStatus = ChecklistStatus.PASSED
    remarks: Optional[str] = None
    evidence_link: Optional[str] = None


class FormWorkflowHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    actor_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    actor_full_name: Optional[str] = None
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    message: Optional[str] = None
    history_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class FormResponseSaveDraft(BaseModel):
    response_data: Optional[Dict[str, Any]] = None
    submission_data: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def unify_draft_data(cls, data: Any):
        if isinstance(data, dict):
            if "response_data" not in data and "submission_data" in data:
                data["response_data"] = data["submission_data"]
            elif "submission_data" not in data and "response_data" in data:
                data["submission_data"] = data["response_data"]
        return data


class FormResponseSubmit(BaseModel):
    response_data: Optional[Dict[str, Any]] = None
    submission_data: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def unify_submit_data(cls, data: Any):
        if isinstance(data, dict):
            if "response_data" not in data and "submission_data" in data:
                data["response_data"] = data["submission_data"]
            elif "submission_data" not in data and "response_data" in data:
                data["submission_data"] = data["response_data"]
        return data


class FormResponseReturnRequest(BaseModel):
    return_reason: str = Field(..., min_length=3, example="Missing eligibility criteria and competition schedule.")
    reviewer_remarks: Optional[str] = None


class FormResponseForwardRequest(BaseModel):
    target_user_id: UUID = Field(..., example="user-uuid")
    message: str = Field(..., min_length=2, example="Forwarding for Vertical Head sign-off.")
    role_label: Optional[str] = "Vertical Head"
    phase_number: Optional[int] = None


class FormResponseReviewRequest(BaseModel):
    action: Optional[str] = "APPROVE"  # "APPROVE" or "RETURN"
    status: Optional[Any] = None
    decision: Optional[Any] = None
    return_reason: Optional[str] = None
    review_comments: Optional[str] = None
    reviewer_remarks: Optional[str] = None
    review_notes: Optional[str] = None
    execute_transformation: bool = True

    @model_validator(mode="before")
    @classmethod
    def unify_review(cls, data: Any):
        if isinstance(data, dict):
            raw_act = data.get("action")
            raw_stat = data.get("status")
            raw_dec = data.get("decision")
            
            stat_val = getattr(raw_stat, "value", str(raw_stat) if raw_stat is not None else "")
            dec_val = getattr(raw_dec, "value", str(raw_dec) if raw_dec is not None else "")
            act_val = getattr(raw_act, "value", str(raw_act) if raw_act is not None else "")

            if not raw_act or raw_act is None:
                target = stat_val or dec_val or "APPROVE"
                if any(x in str(target).upper() for x in ["APPROV", "ACCEPT"]):
                    data["action"] = "APPROVE"
                else:
                    data["action"] = "RETURN"

            notes = data.get("reviewer_remarks") or data.get("review_comments") or data.get("review_notes")
            if notes:
                data["reviewer_remarks"] = notes
                if not data.get("return_reason") and str(data.get("action")).upper() == "RETURN":
                    data["return_reason"] = notes
        return data




class FormResponseDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    form_name: Optional[str] = None
    form_description: Optional[str] = None
    form_purpose: Optional[str] = None
    form_instructions: Optional[str] = None
    form_version_id: UUID
    version_number: Optional[int] = None
    distribution_id: Optional[UUID] = None
    recipient_id: UUID
    recipient_username: Optional[str] = None
    recipient_name: Optional[str] = None
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    status: FormResponseStatus
    response_data: Dict[str, Any]
    submitted_at: Optional[datetime] = None
    resubmitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    return_reason: Optional[str] = None
    reviewer_remarks: Optional[str] = None
    current_reviewer_id: Optional[UUID] = None
    current_reviewer_username: Optional[str] = None
    current_phase: int = 1
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    schema_fields: List[Dict[str, Any]] = Field(default_factory=list)
    reviewers: List[FormReviewerResponse] = Field(default_factory=list)
    checklist_items: List[FormChecklistItemResponse] = Field(default_factory=list)
    workflow_history: List[FormWorkflowHistoryResponse] = Field(default_factory=list)
    transformed_entity_type: Optional[str] = None
    transformed_entity_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime



# Backward compatibility aliases
FormSubmissionCreate = FormResponseSubmit
FormSubmissionReviewRequest = FormResponseReviewRequest
FormSubmissionResponse = FormResponseDetailsResponse


class FormResponseListResponse(BaseModel):
    total: int
    items: List[FormResponseDetailsResponse]


FormSubmissionListResponse = FormResponseListResponse


class FormDashboardStats(BaseModel):
    total_forms: int = 0
    active_forms: int = 0
    published_forms: int = 0
    total_distributions: int = 0
    total_responses: int = 0
    pending_responses: int = 0
    pending_review: int = 0
    under_review: int = 0
    returned: int = 0
    returned_responses: int = 0
    approved: int = 0
    approved_responses: int = 0

