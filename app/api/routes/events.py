"""
Events, Teams & Readiness API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.event import EventStatus
from app.models.user import User
from app.schemas.event import (
    EventAssignPOCRequest,
    EventCreate,
    EventDashboardResponse,
    EventListResponse,
    EventMemberCreate,
    EventMemberResponse,
    EventMemberUpdate,
    EventReadinessItemResponse,
    EventReadinessUpdate,
    EventResponse,
    EventTransitionRequest,
    EventUpdate,
    POCGroupAssignRequest,
    POCGroupResponse,
)
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events & Readiness"])


def _format_event_response(event) -> EventResponse:
    team_profiles = getattr(event, 'event_team_profiles', None)
    team_profile = team_profiles[0] if team_profiles else None
    team_user_id = team_profile.user_id if team_profile else None
    team_username = team_profile.user.username if (team_profile and team_profile.user) else None
    team_name = team_profile.team_name if team_profile else None

    return EventResponse(
        id=event.id,
        vertical_id=event.vertical_id,
        vertical_name=event.vertical.name if event.vertical else None,
        name=event.name,
        description=event.description,
        event_type=event.event_type,
        status=event.status,
        planned_date=event.planned_date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        society_name=event.society_name,
        event_head_id=event.event_head_id,
        event_head_username=event.event_head.username if event.event_head else None,
        primary_poc_id=event.primary_poc_id,
        primary_poc_username=event.primary_poc.username if event.primary_poc else None,
        event_team_user_id=team_user_id,
        event_team_username=team_username,
        event_team_name=team_name,
        created_by_id=event.created_by_id,
        created_by_username=event.created_by.username if event.created_by else None,
        resource_links=event.resource_links or {},
        remarks=event.remarks,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _format_member_response(m) -> EventMemberResponse:
    return EventMemberResponse(
        id=m.id,
        event_id=m.event_id,
        user_id=m.user_id,
        username=m.user.username if m.user else None,
        full_name=m.user.full_name if m.user else None,
        role_in_event=m.role_in_event,
        status=m.status,
        assigned_by_id=m.assigned_by_id,
        assigned_at=m.assigned_at,
        notes=m.notes,
    )


def _format_readiness_response(r) -> EventReadinessItemResponse:
    return EventReadinessItemResponse(
        id=r.id,
        event_id=r.event_id,
        category=r.category,
        title=r.title,
        description=r.description,
        status=r.status,
        assigned_user_id=r.assigned_user_id,
        assigned_username=r.assigned_user.username if r.assigned_user else None,
        deadline=r.deadline,
        completed_at=r.completed_at,
        completed_by_id=r.completed_by_id,
        evidence_link=r.evidence_link,
        remarks=r.remarks,
        updated_at=r.updated_at,
    )


@router.get("", response_model=EventListResponse, dependencies=[Depends(require_permissions(["events.read"]))])
def list_events(
    vertical_id: Optional[UUID] = Query(None),
    status: Optional[EventStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    events, total = service.list_events(
        vertical_id=vertical_id,
        status=status,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    items = [_format_event_response(e) for e in events]
    return EventListResponse(total=total, items=items)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["events.create"]))])
def create_event(
    data: EventCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService
    authority = AuthorityService(db)
    if not (authority.is_executive(current_user.id) or authority.is_admin(current_user.id)):
        raise ForbiddenException("Only SPORTS_CORE, DEPUTY_CORE, or ADMIN executive leadership may create events")


    service = EventService(db)
    event = service.create_event(data, actor_id=current_user.id)
    db.commit()
    return _format_event_response(service.get_event_by_id(event.id))



@router.get("/{event_id}", response_model=EventResponse, dependencies=[Depends(require_permissions(["events.read"]))])
def get_event(
    event_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    return _format_event_response(service.get_event_by_id(event_id, current_user=current_user))


@router.patch("/{event_id}", response_model=EventResponse, dependencies=[Depends(require_permissions(["events.update"]))])
def update_event(
    event_id: UUID,
    data: EventUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    event = service.update_event(event_id, data, actor_id=current_user.id)
    db.commit()
    return _format_event_response(service.get_event_by_id(event.id))


@router.post("/{event_id}/transition", response_model=EventResponse, dependencies=[Depends(require_permissions(["events.transition"]))])
def transition_event(
    event_id: UUID,
    data: EventTransitionRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService
    authority = AuthorityService(db)
    if not (authority.is_executive(current_user.id) or authority.is_admin(current_user.id)):
        raise ForbiddenException("Only SPORTS_CORE, DEPUTY_CORE, or ADMIN executive leadership may transition event status")

    service = EventService(db)
    event = service.transition_event_status(event_id, data, actor_id=current_user.id)
    db.commit()
    return _format_event_response(service.get_event_by_id(event.id))


@router.post("/{event_id}/poc", response_model=EventResponse, dependencies=[Depends(require_permissions(["events.team.manage"]))])
def assign_poc(
    event_id: UUID,
    data: EventAssignPOCRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService
    authority = AuthorityService(db)
    if not (authority.is_executive(current_user.id) or authority.is_admin(current_user.id)):
        raise ForbiddenException("Only SPORTS_CORE, DEPUTY_CORE, or ADMIN executive leadership may manage event POCs")

    service = EventService(db)
    event = service.assign_poc(event_id, data, actor_id=current_user.id)
    db.commit()
    return _format_event_response(service.get_event_by_id(event.id))


@router.post("/{event_id}/poc-group", response_model=POCGroupResponse, dependencies=[Depends(require_permissions(["events.team.manage"]))])
def assign_poc_group(
    event_id: UUID,
    data: POCGroupAssignRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Assigns an authoritative POC group with exactly 1 active Head POC and POC members."""
    from app.core.exceptions import ForbiddenException
    from app.services.authority_service import AuthorityService
    authority = AuthorityService(db)
    if not (authority.is_executive(current_user.id) or authority.is_admin(current_user.id)):
        raise ForbiddenException("Only SPORTS_CORE, DEPUTY_CORE, or ADMIN executive leadership may manage event POCs")

    service = EventService(db)
    poc_group = service.assign_poc_group(event_id, data, actor_id=current_user.id)
    db.commit()
    return poc_group


@router.get("/{event_id}/poc-group", response_model=POCGroupResponse, dependencies=[Depends(require_permissions(["events.read"]))])
def get_poc_group(
    event_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    """Retrieves the active POC group for the Event."""
    service = EventService(db)
    return service.get_poc_group(event_id, current_user=current_user)


@router.get("/{event_id}/team", response_model=List[EventMemberResponse], dependencies=[Depends(require_permissions(["events.read"]))])
def list_event_team(
    event_id: UUID,
    db: Session = Depends(get_db),
):
    service = EventService(db)
    members = service.list_event_members(event_id)
    return [_format_member_response(m) for m in members]


@router.post("/{event_id}/team", response_model=EventMemberResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["events.team.manage"]))])
def add_event_team_member(
    event_id: UUID,
    data: EventMemberCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    member = service.add_event_member(event_id, data, actor_id=current_user.id)
    db.commit()
    return _format_member_response(member)


@router.patch("/{event_id}/team/{member_id}", response_model=EventMemberResponse, dependencies=[Depends(require_permissions(["events.team.manage"]))])
def update_event_team_member(
    event_id: UUID,
    member_id: UUID,
    data: EventMemberUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    member = service.update_event_member(event_id, member_id, data, actor_id=current_user.id)
    db.commit()
    return _format_member_response(member)


@router.get("/{event_id}/readiness", response_model=List[EventReadinessItemResponse], dependencies=[Depends(require_permissions(["events.read"]))])
def list_event_readiness(
    event_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    items = service.list_readiness_items(event_id, current_user=current_user)
    return [_format_readiness_response(r) for r in items]


@router.patch("/{event_id}/readiness/{item_id}", response_model=EventReadinessItemResponse, dependencies=[Depends(require_permissions(["events.readiness.manage"]))])
def update_event_readiness(
    event_id: UUID,
    item_id: UUID,
    data: EventReadinessUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    item = service.update_readiness_item(event_id, item_id, data, actor_id=current_user.id)
    db.commit()
    return _format_readiness_response(item)


@router.get("/{event_id}/dashboard", response_model=EventDashboardResponse, dependencies=[Depends(require_permissions(["events.read"]))])
def get_event_dashboard(
    event_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = EventService(db)
    dash = service.get_event_dashboard(event_id, current_user=current_user)
    return EventDashboardResponse(
        event=_format_event_response(dash["event"]),
        team_members=[_format_member_response(m) for m in dash["team_members"]],
        readiness_items=[_format_readiness_response(r) for r in dash["readiness_items"]],
        readiness_summary=dash["readiness_summary"],
        tasks_count=dash["tasks_count"],
        tasks=dash["tasks"],
        requirements_count=dash["requirements_count"],
        requirements=dash["requirements"],
        meetings_count=dash["meetings_count"],
        meetings=dash["meetings"],
        issues_count=dash["issues_count"],
        issues=dash["issues"],
    )
