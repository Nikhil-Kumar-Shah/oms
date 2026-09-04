"""
Pydantic Schemas for Master Tasks & Task Comments
Paradox Sports OMS - Phase 3 Core Operational System
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.task import TaskHealth, TaskPriority, TaskStatus, TaskType


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class TaskCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    author_username: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskHistoryResponse(BaseModel):
    id: UUID
    task_id: UUID
    actor_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    action: str
    previous_value: Optional[dict] = None
    new_value: Optional[dict] = None
    timestamp: datetime
    correlation_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    # Primary fields
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    task_type: TaskType = TaskType.ROUTINE
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    blockers: Optional[str] = None
    remarks: Optional[str] = None
    evidence_link: Optional[str] = None

    # Self task flag (for My Task workflow)
    is_self_task: bool = False

    # Universal Selector / Audience Target Contract:
    vertical_ids: Optional[List[UUID]] = None
    user_ids: Optional[List[UUID]] = None
    role_ids: Optional[List[str]] = None
    include_all: Optional[bool] = False
    audience: Optional[dict] = None

    # Legacy / Single fields (optional for backward compatibility):
    vertical_id: Optional[UUID] = None
    assigned_to_id: Optional[UUID] = None

    @field_validator(
        "vertical_id", "assigned_to_id", "deadline", "description", "blockers", "remarks", "evidence_link",
        mode="before"
    )
    @classmethod
    def empty_str_to_none_create(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="wrap")
    @classmethod
    def validate_target_specified(cls, values, handler):
        from pydantic_core import PydanticCustomError, ValidationError, InitErrorDetails

        is_self = False
        has_target = False
        if isinstance(values, dict):
            is_self = bool(values.get("is_self_task"))
            has_target = bool(
                values.get("vertical_id")
                or values.get("vertical_ids")
                or values.get("user_ids")
                or values.get("role_ids")
                or values.get("include_all")
                or values.get("audience")
            )

        try:
            instance = handler(values)
            if not is_self and not has_target and not (
                instance.vertical_id
                or instance.vertical_ids
                or instance.user_ids
                or instance.role_ids
                or instance.include_all
                or instance.audience
            ):
                raise ValidationError.from_exception_data(
                    title=cls.__name__,
                    line_errors=[
                        InitErrorDetails(
                            type=PydanticCustomError("missing", "Field required"),
                            loc=("vertical_id",),
                            input=None,
                        )
                    ],
                )
            return instance
        except ValidationError as exc:
            if not is_self and not has_target:
                existing_locs = {err["loc"][-1] for err in exc.errors() if err.get("loc")}
                if "vertical_id" not in existing_locs:
                    errors = list(exc.errors())
                    new_errors = [
                        InitErrorDetails(
                            type=PydanticCustomError("missing", "Field required"),
                            loc=("vertical_id",),
                            input=None,
                        )
                    ]
                    for e in errors:
                        new_errors.append(
                            InitErrorDetails(
                                type=PydanticCustomError(e["type"], e["msg"]),
                                loc=e["loc"],
                                input=e.get("input"),
                            )
                        )
                    raise ValidationError.from_exception_data(
                        title=cls.__name__,
                        line_errors=new_errors,
                    )
            raise exc


class SelfTaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    vertical_id: Optional[UUID] = None
    task_type: TaskType = TaskType.ROUTINE
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    blockers: Optional[str] = None
    remarks: Optional[str] = None
    evidence_link: Optional[str] = None

    @field_validator(
        "vertical_id", "deadline", "description", "blockers", "remarks", "evidence_link",
        mode="before"
    )
    @classmethod
    def empty_str_to_none_self(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    deadline: Optional[datetime] = None
    completion_percentage: Optional[int] = Field(None, ge=0, le=100)
    blockers: Optional[str] = None
    remarks: Optional[str] = None
    latest_update: Optional[str] = None
    evidence_link: Optional[str] = None
    deficiency: Optional[str] = None

    @field_validator(
        "deadline", "description", "blockers", "remarks", "latest_update", "evidence_link", "deficiency",
        mode="before"
    )
    @classmethod
    def empty_str_to_none_update(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TaskTransitionRequest(BaseModel):
    status: TaskStatus
    completion_percentage: Optional[int] = Field(None, ge=0, le=100)
    blockers: Optional[str] = None
    remarks: Optional[str] = None


class TaskAssignRequest(BaseModel):
    assigned_to_id: Optional[UUID] = None

    @field_validator("assigned_to_id", mode="before")
    @classmethod
    def empty_str_to_none_assign(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TaskReassignRequest(BaseModel):
    new_assigned_to_id: UUID = Field(..., description="Target assignee user ID within task vertical")
    remarks: Optional[str] = None

    @field_validator("remarks", mode="before")
    @classmethod
    def empty_str_to_none_reassign(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TaskEscalateRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000, description="Detailed operational escalation reason")
    escalated_to_id: Optional[UUID] = None
    remarks: Optional[str] = None


class TaskResolveEscalationRequest(BaseModel):
    resolution: str = Field(..., min_length=3, max_length=2000, description="Escalation resolution details")
    remarks: Optional[str] = None


class TaskBlockRequest(BaseModel):
    blocker_description: str = Field(..., min_length=3, max_length=2000, description="Description of the blocker")


class TaskUnblockRequest(BaseModel):
    resolution: Optional[str] = Field(None, max_length=2000, description="Resolution remarks for unblocking")


class TaskResponse(BaseModel):
    id: UUID
    vertical_id: UUID
    vertical_name: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    assigned_to_username: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_by_id: UUID
    assigned_by_username: Optional[str] = None
    title: str
    description: Optional[str] = None
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    completion_percentage: int
    health: TaskHealth
    date_assigned: datetime
    deadline: Optional[datetime] = None
    completed_on: Optional[datetime] = None
    blockers: Optional[str] = None
    remarks: Optional[str] = None
    latest_update: Optional[str] = None
    evidence_link: Optional[str] = None
    deficiency: Optional[str] = None
    is_escalated: bool = False
    escalated_to_id: Optional[UUID] = None
    escalated_to_username: Optional[str] = None
    escalation_reason: Optional[str] = None
    escalated_at: Optional[datetime] = None
    escalation_status: Optional[str] = None
    escalation_resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    total: int
    items: List[TaskResponse]
