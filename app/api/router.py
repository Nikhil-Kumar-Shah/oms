from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user
from app.models.user import User
from app.api.routes import (
    admin,
    analytics,
    announcements,
    auth,
    calendar,
    communications,
    directives,
    event_teams,
    events,
    faqs,
    forms,
    health,
    issues,
    meetings,
    notifications,
    organization,
    profiles,
    reports,
    requirements,
    tasks,
    test_records,
    transfers,
    users_selector,
    workspace,
)

api_v1_router = APIRouter(prefix="/api/v1")

# Foundation & Phase 2 Routers
api_v1_router.include_router(health.router)
api_v1_router.include_router(test_records.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(organization.router)
api_v1_router.include_router(users_selector.router)
api_v1_router.include_router(admin.router)

# Phase 3: Core Operational System
api_v1_router.include_router(tasks.tasks_router)
api_v1_router.include_router(calendar.calendar_router)
api_v1_router.include_router(issues.issues_router)
api_v1_router.include_router(reports.reports_router)

# Phase 4: Event + Coordination System
api_v1_router.include_router(events.router)
api_v1_router.include_router(requirements.router)
api_v1_router.include_router(meetings.router)
api_v1_router.include_router(forms.router)

# Phase 5: Communication + Governance + Analytics
api_v1_router.include_router(announcements.router)
api_v1_router.include_router(directives.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(communications.router)
api_v1_router.include_router(transfers.router)
api_v1_router.include_router(analytics.analytics_router)
api_v1_router.include_router(analytics.reports_router)

# Phase 1: Operational Workspace Enhancements & Event Teams
api_v1_router.include_router(workspace.router)
api_v1_router.include_router(profiles.router)
api_v1_router.include_router(event_teams.router)
api_v1_router.include_router(faqs.router)


@api_v1_router.get(
    "",
    summary="API v1 Discovery & Resource Registry",
    description="Provides API metadata, OpenAPI documentation links, and registered resource groups (Authenticated users only).",
    tags=["API Discovery"],
)
async def api_v1_discovery(current_user: User = Depends(get_current_user)):
    """Returns authenticated developer-facing API discovery metadata and available resource endpoints."""
    return {
        "name": "Paradox Sports Operations Management System (OMS) API",
        "version": "v1",
        "status": "operational",
        "authenticated_as": current_user.username,
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
        "resource_groups": [
            {"group": "Health & System", "prefix": "/api/v1/health", "description": "Database connectivity and liveness probes"},
            {"group": "Authentication", "prefix": "/api/v1/auth", "description": "Login, logout, session refresh, and password management"},
            {"group": "Organization & Verticals", "prefix": "/api/v1/organizations", "description": "Organization entities and vertical divisions"},
            {"group": "Administration", "prefix": "/api/v1/admin", "description": "User lifecycle, role assignment, configuration, and audit log inspection"},
            {"group": "Master Tasks", "prefix": "/api/v1/tasks", "description": "Master Task management, status transitions, health calculation, and audit history"},
            {"group": "Operational Workspace", "prefix": "/api/v1/workspace", "description": "Derived personal My Work projections and unified operational duties"},
            {"group": "Master Calendar", "prefix": "/api/v1/calendar", "description": "Aggregated chronological timeline of task deadlines and meetings"},
            {"group": "Issues & Escalations", "prefix": "/api/v1/issues", "description": "Issue tracking, sensitivity scoping, and escalation resolution"},
            {"group": "Operational Reports", "prefix": "/api/v1/reports", "description": "Daily and weekly work reporting with four-eyes review"},
            {"group": "Events & Operations", "prefix": "/api/v1/events", "description": "Event management, readiness checklists, POC assignment, and rosters"},
            {"group": "Event Teams", "prefix": "/api/v1/event-teams", "description": "External event team operational profiles and boundary isolation"},
            {"group": "Requirements", "prefix": "/api/v1/requirements", "description": "Cross-vertical resource requirements, assignments, and escalations"},
            {"group": "Meetings & RSVPs", "prefix": "/api/v1/meetings", "description": "Meeting scheduling, participant RSVPs, action items, and task conversion"},
            {"group": "Dynamic Forms", "prefix": "/api/v1/forms", "description": "Dynamic form builder, versioning, submissions, and atomic entity transformation"},
            {"group": "Announcements", "prefix": "/api/v1/announcements", "description": "Scoped informational announcements with event team isolation"},
            {"group": "Directives", "prefix": "/api/v1/directives", "description": "Operational directives with individual acknowledgement rosters"},
            {"group": "Notifications", "prefix": "/api/v1/notifications", "description": "Personalized user attention notifications with ownership isolation"},
            {"group": "Communications Tracker", "prefix": "/api/v1/communications", "description": "Official correspondence logs with vertical and event linkage"},
            {"group": "Governed Transfers", "prefix": "/api/v1/transfers", "description": "Four-eyes governed resource ownership transfers"},
            {"group": "Operational Analytics", "prefix": "/api/v1/analytics", "description": "Real-time PostgreSQL metrics, KPI indicators, and compliance reports"},
        ],
    }
