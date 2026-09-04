"""
Tests for Operational Analytics & Administrative Reporting
"""

import pytest
from app.services.admin_reporting_service import AdminReportingService
from app.services.analytics_service import AnalyticsService


def test_operational_analytics_generation(db_session, test_vertical):
    """Verifies operational metrics aggregation via PostgreSQL."""
    service = AnalyticsService(db_session)
    op = service.get_operational_analytics(vertical_id=test_vertical.id)

    assert op.generated_at is not None
    assert op.tasks_total >= 0
    assert op.issues_total >= 0
    assert op.events_total >= 0
    assert op.meetings_total >= 0
    assert 0.0 <= op.tasks_completion_rate_pct <= 100.0


def test_administrative_analytics_generation(db_session):
    """Verifies administrative organization-wide analytics."""
    service = AnalyticsService(db_session)
    admin_op = service.get_administrative_analytics()

    assert admin_op.organization_name is not None
    assert admin_op.total_verticals >= 1
    assert admin_op.total_users >= 1
    assert admin_op.system_config_keys_count >= 1


def test_my_summary_analytics(db_session, test_user):
    """Verifies personal executive summary aggregation."""
    service = AnalyticsService(db_session)
    summary = service.get_my_summary(user=test_user)

    assert summary.user_id == test_user.id
    assert summary.username == test_user.username
    assert summary.my_tasks_total >= 0


def test_admin_reports_generation(db_session):
    """Verifies administrative reporting service for tasks, events, issues, meetings."""
    rep_service = AdminReportingService(db_session)

    t_rep = rep_service.get_task_completion_report()
    assert t_rep.report_name == "Task Completion & Workload Report"
    assert t_rep.total_records >= 0

    e_rep = rep_service.get_event_readiness_report()
    assert e_rep.report_name == "Event Readiness & Checklist Report"

    i_rep = rep_service.get_issue_escalation_report()
    assert i_rep.report_name == "Issue & Escalation Register Report"

    m_rep = rep_service.get_meeting_attendance_report()
    assert m_rep.report_name == "Meeting Participation & RSVP Report"
