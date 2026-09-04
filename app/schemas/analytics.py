"""
Analytics & Administrative Reporting Schemas
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class OperationalAnalyticsResponse(BaseModel):
    vertical_id: Optional[UUID] = None
    vertical_name: Optional[str] = None
    generated_at: datetime

    # Tasks
    tasks_total: int
    tasks_active: int
    tasks_completed: int
    tasks_overdue: int
    tasks_blocked: int
    tasks_completion_rate_pct: float

    # Issues
    issues_total: int
    issues_open: int
    issues_escalated: int
    issues_resolved: int

    # Requirements
    requirements_total: int
    requirements_open: int
    requirements_in_progress: int
    requirements_completed: int

    # Events
    events_total: int
    events_planning: int
    events_in_progress: int
    events_completed: int
    readiness_completed_pct: float

    # Meetings
    meetings_total: int
    meetings_scheduled: int
    meetings_completed: int
    meetings_rsvp_accepted_pct: float

    # Reports
    daily_reports_submitted_last_7d: int
    weekly_reports_submitted_last_4w: int

    # Forms
    forms_total: int
    form_submissions_total: int
    form_submissions_pending: int


class AdministrativeAnalyticsResponse(BaseModel):
    generated_at: datetime
    organization_name: str
    total_verticals: int
    total_users: int
    active_users: int

    # System-wide metrics
    global_tasks_total: int
    global_tasks_completion_rate: float
    global_overdue_tasks: int

    global_open_issues: int
    global_critical_issues: int

    global_active_events: int
    global_event_readiness_avg_pct: float

    global_active_directives: int
    directive_acknowledgement_compliance_pct: float

    reporting_compliance_rate_pct: float
    system_config_keys_count: int
    audit_events_last_24h: int


class MySummaryAnalyticsResponse(BaseModel):
    user_id: UUID
    username: str
    generated_at: datetime

    my_tasks_total: int
    my_tasks_in_progress: int
    my_tasks_completed: int
    my_tasks_overdue: int

    my_assigned_requirements_total: int
    my_open_requirements: int

    my_upcoming_meetings_count: int
    my_pending_rsvps_count: int

    my_pending_directive_acknowledgements: int
    my_unread_notifications_count: int
    my_daily_report_submitted_today: bool


class OperationalDashboardResponse(BaseModel):
    generated_at: datetime
    active_tasks: int
    completed_tasks: int
    overdue_tasks: int
    blocked_tasks: int
    open_issues: int
    escalated_issues: int
    upcoming_meetings: int
    pending_requirements: int
    event_readiness_avg_pct: float
    reporting_compliance_pct: float
    pending_directives: int
    outstanding_approvals: int


class PerformanceIndicatorsResponse(BaseModel):
    generated_at: datetime
    task_completion_rate_pct: float
    overdue_task_rate_pct: float
    issue_resolution_rate_pct: float
    requirement_resolution_rate_pct: float
    meeting_rsvp_rate_pct: float
    reporting_compliance_rate_pct: float
    event_readiness_avg_pct: float
    escalation_rate_pct: float


class AdminReportResponse(BaseModel):
    report_name: str
    generated_at: datetime
    total_records: int
    summary: Dict[str, Any] = {}
    records: List[Dict[str, Any]]
