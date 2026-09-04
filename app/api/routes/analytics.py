"""
Operational Analytics & Administrative Reporting API Endpoints
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.user import User
from app.schemas.analytics import (
    AdminReportResponse,
    AdministrativeAnalyticsResponse,
    MySummaryAnalyticsResponse,
    OperationalAnalyticsResponse,
    OperationalDashboardResponse,
    PerformanceIndicatorsResponse,
)
from app.services.admin_reporting_service import AdminReportingService
from app.services.analytics_service import AnalyticsService

analytics_router = APIRouter(prefix="/analytics", tags=["Operational Analytics"])
reports_router = APIRouter(prefix="/admin/reports", tags=["Administrative Reporting"])


@analytics_router.get("/dashboard", response_model=OperationalDashboardResponse, dependencies=[Depends(require_permissions(["analytics.read"]))])
def get_operational_dashboard(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)
    return service.get_operational_dashboard(current_user=current_user)


@analytics_router.get("/indicators", response_model=PerformanceIndicatorsResponse, dependencies=[Depends(require_permissions(["analytics.read"]))])
def get_performance_indicators(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)
    return service.get_performance_indicators(current_user=current_user)



@analytics_router.get("/operational", response_model=OperationalAnalyticsResponse, dependencies=[Depends(require_permissions(["analytics.read"]))])
def get_operational_analytics(
    vertical_id: Optional[UUID] = Query(None),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.services.authority_service import AuthorityService
    auth_service = AuthorityService(db)
    scoped_vid = vertical_id
    if not auth_service.is_executive_or_admin(current_user.id):
        user_vids = auth_service.get_user_vertical_ids(current_user.id)
        if scoped_vid:
            if scoped_vid not in user_vids:
                scoped_vid = user_vids[0] if user_vids else None
        else:
            scoped_vid = user_vids[0] if user_vids else None

    service = AnalyticsService(db)
    return service.get_operational_analytics(vertical_id=scoped_vid)


@analytics_router.get("/administrative", response_model=AdministrativeAnalyticsResponse, dependencies=[Depends(require_permissions(["analytics.admin"]))])
def get_administrative_analytics(
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)
    return service.get_administrative_analytics()


@analytics_router.get("/my-summary", response_model=MySummaryAnalyticsResponse, dependencies=[Depends(require_permissions(["analytics.read"]))])
def get_my_summary(
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)
    return service.get_my_summary(user=current_user)


# -----------------------------------------------------------------------------
# Administrative Reports
# -----------------------------------------------------------------------------

@reports_router.get("/tasks", response_model=AdminReportResponse, dependencies=[Depends(require_permissions(["reports.admin"]))])
def get_task_completion_report(
    vertical_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    service = AdminReportingService(db)
    return service.get_task_completion_report(vertical_id=vertical_id)


@reports_router.get("/events", response_model=AdminReportResponse, dependencies=[Depends(require_permissions(["reports.admin"]))])
def get_event_readiness_report(
    db: Session = Depends(get_db),
):
    service = AdminReportingService(db)
    return service.get_event_readiness_report()


@reports_router.get("/issues", response_model=AdminReportResponse, dependencies=[Depends(require_permissions(["reports.admin"]))])
def get_issue_escalation_report(
    db: Session = Depends(get_db),
):
    service = AdminReportingService(db)
    return service.get_issue_escalation_report()


@reports_router.get("/meetings", response_model=AdminReportResponse, dependencies=[Depends(require_permissions(["reports.admin"]))])
def get_meeting_attendance_report(
    db: Session = Depends(get_db),
):
    service = AdminReportingService(db)
    return service.get_meeting_attendance_report()


@reports_router.get("/compliance", response_model=AdminReportResponse, dependencies=[Depends(require_permissions(["reports.admin"]))])
def get_reporting_compliance_report(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    service = AdminReportingService(db)
    return service.get_reporting_compliance_report(days=days)
