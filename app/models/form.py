"""
Advanced Forms, Form Versions, Distributions, Responses & Multi-Phase Review Workflow Models
Paradox Sports OMS - Phase 11 Form & Response Workflow System
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FormStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class FormAudience(str, enum.Enum):
    ALL = "ALL"
    ORGANIZATION = "ORGANIZATION"
    VERTICAL = "VERTICAL"
    SPECIFIC_ROLES = "SPECIFIC_ROLES"
    EVENT = "EVENT"
    EVENT_TEAM = "EVENT_TEAM"


class FormResponseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETURNED = "RETURNED"
    RESUBMITTED = "RESUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# Backward compatibility alias
FormSubmissionStatus = FormResponseStatus


class FormFieldType(str, enum.Enum):
    TEXT = "TEXT"
    LONG_TEXT = "LONG_TEXT"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    SELECT = "SELECT"
    MULTI_SELECT = "MULTI_SELECT"
    CHECKBOX = "CHECKBOX"
    RADIO = "RADIO"
    YES_NO = "YES_NO"
    REFERENCE_LINK = "REFERENCE_LINK"
    URL = "URL"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    USER_REFERENCE = "USER_REFERENCE"
    VERTICAL_REFERENCE = "VERTICAL_REFERENCE"


class ChecklistStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


class Form(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forms"

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    purpose = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, default="Operational")
    status = Column(
        Enum(FormStatus, name="form_status_enum", native_enum=True),
        nullable=False,
        default=FormStatus.DRAFT,
        index=True,
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vertical_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_audience = Column(
        Enum(FormAudience, name="form_audience_enum", native_enum=True),
        nullable=False,
        default=FormAudience.ORGANIZATION,
    )
    current_version_number = Column(Integer, nullable=False, default=1)
    distribution_config = Column(JSONB, nullable=True, default=dict)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id], backref="owned_forms")
    vertical = relationship("Vertical", foreign_keys=[vertical_id], backref="forms")
    event = relationship("Event", foreign_keys=[event_id], backref="forms")
    versions = relationship("FormVersion", back_populates="form", cascade="all, delete-orphan", order_by="FormVersion.version_number")
    distributions = relationship("FormDistribution", back_populates="form", cascade="all, delete-orphan", order_by="desc(FormDistribution.created_at)")
    responses = relationship("FormResponse", back_populates="form", cascade="all, delete-orphan")
    submissions = relationship("FormResponse", back_populates="form", overlaps="responses")

    def __repr__(self) -> str:
        return f"<Form(id={self.id}, name='{self.name}', status='{self.status}')>"


class FormVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "form_versions"
    __table_args__ = (
        UniqueConstraint("form_id", "version_number", name="uq_form_version_form_number"),
    )

    form_id = Column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    sections = Column(JSONB, nullable=False, default=list)  # List of Section objects with nested fields
    schema = Column(JSONB, nullable=False, default=list)  # Flat list of all fields
    transformation_config = Column(JSONB, nullable=True)  # Transformation rules on approval
    review_config = Column(JSONB, nullable=True)  # Default multi-phase review checklist configuration
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    form = relationship("Form", back_populates="versions")
    published_by = relationship("User", foreign_keys=[published_by_id])
    distributions = relationship("FormDistribution", back_populates="form_version")
    responses = relationship("FormResponse", back_populates="form_version")
    submissions = relationship("FormResponse", back_populates="form_version", overlaps="responses")

    def __repr__(self) -> str:
        return f"<FormVersion(form_id={self.form_id}, version={self.version_number}, is_published={self.is_published})>"


class FormDistribution(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "form_distributions"

    form_id = Column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    form_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    distributor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=True)
    instructions = Column(Text, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    recipient_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    form = relationship("Form", back_populates="distributions")
    form_version = relationship("FormVersion", back_populates="distributions")
    distributor = relationship("User", foreign_keys=[distributor_id], backref="distributed_forms")
    responses = relationship("FormResponse", back_populates="distribution", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FormDistribution(id={self.id}, form_id={self.form_id}, recipients={self.recipient_count})>"


class FormResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "form_responses"

    form_id = Column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    form_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    distribution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_distributions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_team_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("event_team_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        Enum(FormResponseStatus, name="form_response_status_enum", native_enum=True),
        nullable=False,
        default=FormResponseStatus.ASSIGNED,
        index=True,
    )
    response_data = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    resubmitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    return_reason = Column(Text, nullable=True)
    reviewer_remarks = Column(Text, nullable=True)
    current_reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_phase = Column(Integer, nullable=False, default=1)
    transformed_entity_type = Column(String(64), nullable=True)
    transformed_entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Aliases for backward compatibility
    @property
    def submitter_id(self):
        return self.recipient_id

    @submitter_id.setter
    def submitter_id(self, val):
        self.recipient_id = val

    @property
    def submitter(self):
        return self.recipient

    @property
    def submission_data(self):
        return self.response_data

    @submission_data.setter
    def submission_data(self, val):
        self.response_data = val

    @property
    def reviewer_id(self):
        return self.current_reviewer_id

    @reviewer_id.setter
    def reviewer_id(self, val):
        self.current_reviewer_id = val

    @property
    def reviewer(self):
        return self.current_reviewer

    @property
    def review_comments(self):
        return self.reviewer_remarks

    @review_comments.setter
    def review_comments(self, val):
        self.reviewer_remarks = val

    # Relationships
    form = relationship("Form", back_populates="responses")
    form_version = relationship("FormVersion", back_populates="responses")
    distribution = relationship("FormDistribution", back_populates="responses")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="form_responses")
    event = relationship("Event", foreign_keys=[event_id])
    event_team_profile = relationship("EventTeamProfile", foreign_keys=[event_team_profile_id])
    current_reviewer = relationship("User", foreign_keys=[current_reviewer_id])
    reviewers = relationship("FormReviewer", back_populates="response", cascade="all, delete-orphan", order_by="FormReviewer.phase_number")
    checklist_items = relationship("FormChecklistItem", back_populates="response", cascade="all, delete-orphan", order_by="FormChecklistItem.phase_number, FormChecklistItem.created_at")
    workflow_history = relationship("FormWorkflowHistory", back_populates="response", cascade="all, delete-orphan", order_by="desc(FormWorkflowHistory.created_at)")

    def __repr__(self) -> str:
        return f"<FormResponse(id={self.id}, form_id={self.form_id}, recipient_id={self.recipient_id}, status='{self.status}')>"


# Backward compatibility alias
FormSubmission = FormResponse


class FormReviewer(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "form_reviewers"

    response_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_label = Column(String(100), nullable=False, default="Reviewer")
    phase_number = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="PENDING")
    decision_comments = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    response = relationship("FormResponse", back_populates="reviewers")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<FormReviewer(response_id={self.response_id}, user_id={self.user_id}, role='{self.role_label}', phase={self.phase_number})>"


class FormChecklistItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "form_checklist_items"

    response_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_number = Column(Integer, nullable=False, default=1)
    phase_name = Column(String(100), nullable=False, default="Phase Review")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        Enum(ChecklistStatus, name="checklist_status_enum", native_enum=True),
        nullable=False,
        default=ChecklistStatus.PENDING,
    )
    remarks = Column(Text, nullable=True)
    evidence_link = Column(String(1000), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    response = relationship("FormResponse", back_populates="checklist_items")
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    def __repr__(self) -> str:
        return f"<FormChecklistItem(id={self.id}, title='{self.title}', status='{self.status}')>"


class FormWorkflowHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "form_workflow_history"

    response_id = Column(
        UUID(as_uuid=True),
        ForeignKey("form_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(100), nullable=False)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=True)
    message = Column(Text, nullable=True)
    history_metadata = Column(JSONB, nullable=True, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    response = relationship("FormResponse", back_populates="workflow_history")
    actor = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<FormWorkflowHistory(id={self.id}, action='{self.action}', created_at='{self.created_at}')>"
