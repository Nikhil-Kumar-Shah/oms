"""
Event Team API Endpoints
Paradox Sports OMS - Phase 1 Organization + People + Role Governance

Provides endpoints for creating, activating, and managing Event Team accounts and profiles.
Enforces:
- Admin creates credentials (unactivated, cannot log in)
- Sports Core / Deputy Core activates accounts (binding Event Team -> Event Team Account -> Event Head -> POCs)
- Event Overview and POC Roster dashboard support
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_role
from app.core.database import get_db
from app.core.exceptions import ForbiddenException
from app.models.user import AccountStatus, User
from app.schemas.event_team import (
    EventTeamActivate,
    EventTeamCreate,
    EventTeamCredentialsCreate,
    EventTeamListResponse,
    EventTeamProfileResponse,
    EventTeamUpdate,
    UnactivatedAccountResponse,
)
from app.services.event_team_service import EventTeamService

router = APIRouter(prefix="/event-teams", tags=["Event Teams"])


def _format_event_team_response(profile, db: Session) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    counts = service.get_event_team_activity_counts(profile.event_id)

    # Resolve Head POC details
    contact_info = dict(profile.contact_info or {})
    head_poc_id_str = contact_info.get("head_poc_id")
    head_poc_id = UUID(head_poc_id_str) if head_poc_id_str else (profile.event.primary_poc_id if profile.event else None)

    head_poc_name = contact_info.get("head_poc_name")
    head_poc_username = contact_info.get("head_poc_username")
    if head_poc_id and not head_poc_name:
        poc_user = db.get(User, head_poc_id)
        if poc_user:
            head_poc_name = poc_user.full_name
            head_poc_username = poc_user.username

    # Resolve Additional POCs
    additional_pocs = []
    add_poc_id_strs = contact_info.get("additional_poc_ids", [])
    for pid_str in add_poc_id_strs:
        try:
            pid = UUID(pid_str)
            pu = db.get(User, pid)
            if pu:
                additional_pocs.append({
                    "id": str(pu.id),
                    "name": pu.full_name,
                    "username": pu.username,
                    "email": pu.email,
                })
        except Exception:
            continue

    user_status = profile.user.account_status.value if profile.user else "UNKNOWN"
    is_activated = bool(user_status == AccountStatus.ACTIVE.value and contact_info.get("is_activated", True))

    return EventTeamProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        username=profile.user.username if profile.user else None,
        account_status=user_status,
        is_activated=is_activated,
        event_id=profile.event_id,
        event_name=profile.event.name if profile.event else None,
        event_date=profile.event.planned_date.isoformat() if (profile.event and profile.event.planned_date) else None,
        event_status=profile.event.status.value if profile.event else None,
        team_name=profile.team_name,
        head_name=profile.head_name,
        head_email=profile.head_email,
        head_phone=profile.head_phone,
        head_poc_id=head_poc_id,
        head_poc_name=head_poc_name,
        head_poc_username=head_poc_username,
        additional_pocs=additional_pocs,
        members_summary=profile.members_summary or [],
        contact_info=contact_info,
        event_metadata=profile.event_metadata or {},
        notes=profile.notes,
        requirements_count=counts["requirements_count"],
        issues_count=counts["issues_count"],
        meetings_count=counts["meetings_count"],
        members_count=counts["members_count"],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "/credentials",
    response_model=UnactivatedAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin Create Event Team Credentials",
    description="Admin creates Event Team account credentials. Account remains unactivated (DISABLED) until Sports Core / Deputy Core activates it.",
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_event_team_credentials(
    payload: EventTeamCredentialsCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnactivatedAccountResponse:
    service = EventTeamService(db)
    user, _ = service.create_event_team_credentials(payload, actor_id=current_user.id)
    db.commit()
    return UnactivatedAccountResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        account_status=user.account_status.value,
        created_at=user.created_at,
    )


@router.get(
    "/unactivated",
    response_model=List[UnactivatedAccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List Unactivated Event Team Accounts",
    description="Lists Event Team user accounts awaiting activation by Sports Core or Deputy Core.",
    dependencies=[Depends(require_role("ADMIN", "SPORTS_CORE", "DEPUTY_CORE"))],
)
def list_unactivated_accounts(
    db: Session = Depends(get_db),
) -> List[UnactivatedAccountResponse]:
    service = EventTeamService(db)
    users = service.list_unactivated_accounts()
    return [
        UnactivatedAccountResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            account_status=u.account_status.value,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post(
    "/activate",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Event Team Account",
    description="Sports Core or Deputy Core activates an Event Team account, binding Event Team -> Account -> Event Head -> POCs.",
    dependencies=[Depends(require_role("SPORTS_CORE", "DEPUTY_CORE", "ADMIN"))],
)
def activate_event_team(
    payload: EventTeamActivate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    profile = service.activate_event_team(payload, actor_id=current_user.id)
    db.commit()
    return _format_event_team_response(service.get_event_team_by_id(profile.id), db)


@router.post(
    "",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Event Team Account & Profile",
    description="Creates an Event Team account and associated profile.",
    dependencies=[Depends(require_role("ADMIN", "SPORTS_CORE", "DEPUTY_CORE"))],
)
def create_event_team(
    payload: EventTeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    profile = service.create_event_team(payload, actor_id=current_user.id)
    db.commit()
    return _format_event_team_response(service.get_event_team_by_id(profile.id), db)


@router.get(
    "/me",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Event Team Profile",
    description="Returns the Event Team profile associated with the currently authenticated user.",
)
def get_my_event_team(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    is_active, reason = service.is_event_team_fully_activated(current_user.id)
    if not is_active:
        raise ForbiddenException(f"Event Team account is not activated: {reason}")
    profile = service.get_event_team_by_user_id(current_user.id)
    return _format_event_team_response(profile, db)


@router.put(
    "/me",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Current Event Team Profile",
    description="Allows an authenticated Event Team account to update its operational contact info and members summary.",
)
def update_my_event_team(
    payload: EventTeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    is_active, reason = service.is_event_team_fully_activated(current_user.id)
    if not is_active:
        raise ForbiddenException(f"Event Team account is not activated: {reason}")
    profile = service.get_event_team_by_user_id(current_user.id)
    updated = service.update_event_team(profile.id, payload, actor_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_event_team_response(updated, db)


@router.get(
    "/{team_id}",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Event Team Profile",
    description="Retrieves a specific Event Team profile by ID.",
)
def get_event_team(
    team_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    profile = service.get_event_team_by_id(team_id, current_user=current_user)
    return _format_event_team_response(profile, db)


@router.put(
    "/{team_id}",
    response_model=EventTeamProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Event Team Profile",
    description="Updates operational metadata for an Event Team.",
    dependencies=[Depends(require_role("ADMIN", "SPORTS_CORE", "DEPUTY_CORE", "SUPER_COORDINATOR"))],
)
def update_event_team(
    team_id: UUID,
    payload: EventTeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTeamProfileResponse:
    service = EventTeamService(db)
    updated = service.update_event_team(team_id, payload, actor_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_event_team_response(updated, db)


@router.get(
    "",
    response_model=EventTeamListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Event Teams",
    description="Lists Event Team profiles, optionally filtered by target Event.",
    dependencies=[Depends(require_role("ADMIN", "SPORTS_CORE", "DEPUTY_CORE", "SUPER_COORDINATOR", "COORDINATOR"))],
)
def list_event_teams(
    event_id: Optional[UUID] = Query(None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> EventTeamListResponse:
    service = EventTeamService(db)
    items, total = service.list_event_teams(event_id=event_id, limit=limit, offset=offset)
    return EventTeamListResponse(
        total=total,
        items=[_format_event_team_response(p, db) for p in items],
    )
