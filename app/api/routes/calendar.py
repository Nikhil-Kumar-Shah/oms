"""
Master & Personal Calendar API Endpoints
Paradox Sports OMS - Phase 10G Architecture
"""

import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, ValidationException
from app.models.calendar import ActivityCategory, CalendarAudience, CalendarPriority, CalendarStatus
from app.models.user import User
from app.schemas.calendar import (
    CalendarActionRequest,
    CalendarCreate,
    CalendarListResponse,
    CalendarRescheduleRequest,
    CalendarResponse,
    CalendarUpdate,
)
from app.services.calendar_service import CalendarService

calendar_router = APIRouter(prefix="/calendar", tags=["Master & Personal Calendar"])


def _format_calendar_response(entry, current_user_id: Optional[uuid.UUID] = None) -> CalendarResponse:
    """Helper to convert calendar model to response schema."""
    target_uids = [eu.user_id for eu in entry.entry_users] if getattr(entry, "entry_users", None) else []
    is_personal = (
        entry.audience == CalendarAudience.SPECIFIC_USERS
        and len(target_uids) == 1
        and target_uids[0] == entry.created_by_id
    )
    is_user_completed = False
    user_completed_at = None
    if current_user_id and getattr(entry, "entry_users", None):
        user_eu = next((eu for eu in entry.entry_users if eu.user_id == current_user_id), None)
        if user_eu and user_eu.is_completed:
            is_user_completed = True
            user_completed_at = user_eu.completed_at

    return CalendarResponse(
        id=entry.id,
        title=entry.title,
        description=entry.description,
        activity_date=entry.activity_date,
        start_time=entry.start_time,
        end_time=entry.end_time,
        category=entry.category,
        priority=entry.priority,
        status=entry.status,
        deadline_type=entry.deadline_type,
        audience=entry.audience,
        vertical_id=entry.vertical_id,
        vertical_name=entry.vertical.name if entry.vertical else None,
        event_reference=entry.event_reference,
        resource_link=entry.resource_link,
        remarks=entry.remarks,
        recurrence=entry.recurrence,
        recurrence_end_date=entry.recurrence_end_date,
        entity_type=entry.entity_type or "CALENDAR_ENTRY",
        entity_id=entry.entity_id or entry.id,
        is_personal=is_personal,
        task_id=entry.task_id,
        event_id=entry.event_id,
        meeting_id=entry.meeting_id,
        requirement_id=entry.requirement_id,
        created_by_id=entry.created_by_id,
        created_by_username=entry.created_by.username if entry.created_by else None,
        target_user_ids=target_uids,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        original_date=entry.original_date,
        rescheduled_at=entry.rescheduled_at,
        is_user_completed=is_user_completed,
        user_completed_at=user_completed_at,
    )


@calendar_router.get("", response_model=CalendarListResponse)
async def list_calendar_entries(
    view: Optional[str] = Query(None, description="Calendar view: 'personal' or 'master'"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[ActivityCategory] = Query(None),
    priority: Optional[CalendarPriority] = Query(None),
    status: Optional[CalendarStatus] = Query(None),
    vertical_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists calendar items for the requested view mode.
    - If view is not specified: defaults to 'master' for executive roles (ADMIN, SPORTS_CORE, DEPUTY_CORE)
      and 'personal' for all other roles.
    - 'personal': Synthesizes personal activities + assigned tasks + meetings + events.
    - 'master': Organizational calendar, strictly guarded by calendar.read_master / executive role.
    """
    service = CalendarService(db)
    is_exec = service.authority.is_executive_or_admin(current_user.id)
    target_view = view.lower() if view else ("master" if is_exec else "personal")

    if target_view == "master":
        items, total = service.list_master_calendar(
            user=current_user,
            start_date=start_date,
            end_date=end_date,
            category=category,
            priority=priority,
            status=status,
            vertical_id=vertical_id,
            skip=skip,
            limit=limit,
        )
    else:
        items, total = service.list_personal_calendar(
            user=current_user,
            start_date=start_date,
            end_date=end_date,
            category=category,
            priority=priority,
            status=status,
            vertical_id=vertical_id,
            skip=skip,
            limit=limit,
        )
    return CalendarListResponse(total=total, items=items)


@calendar_router.get("/personal", response_model=CalendarListResponse)
async def list_personal_calendar(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[ActivityCategory] = Query(None),
    priority: Optional[CalendarPriority] = Query(None),
    status: Optional[CalendarStatus] = Query(None),
    vertical_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Direct endpoint for user's personal calendar."""
    service = CalendarService(db)
    items, total = service.list_personal_calendar(
        user=current_user,
        start_date=start_date,
        end_date=end_date,
        category=category,
        priority=priority,
        status=status,
        vertical_id=vertical_id,
        skip=skip,
        limit=limit,
    )
    return CalendarListResponse(total=total, items=items)


@calendar_router.get("/master", response_model=CalendarListResponse)
async def list_master_calendar(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[ActivityCategory] = Query(None),
    priority: Optional[CalendarPriority] = Query(None),
    status: Optional[CalendarStatus] = Query(None),
    vertical_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Direct endpoint for Master Calendar.
    Strictly guarded: non-authorized users receive 403 Forbidden.
    """
    service = CalendarService(db)
    items, total = service.list_master_calendar(
        user=current_user,
        start_date=start_date,
        end_date=end_date,
        category=category,
        priority=priority,
        status=status,
        vertical_id=vertical_id,
        skip=skip,
        limit=limit,
    )
    return CalendarListResponse(total=total, items=items)


@calendar_router.post("", response_model=CalendarResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar_entry(
    data: CalendarCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a calendar entry.
    - If is_personal=True: Allows any user to create a personal activity without requiring calendar.create or vertical division.
    - If is_personal=False: Requires calendar.create permission or executive role.
    """
    service = CalendarService(db)
    entry = service.create_entry(data, actor_id=current_user.id)
    db.commit()
    refreshed = service.get_entry_by_id(entry.id)
    return _format_calendar_response(refreshed)


@calendar_router.get("/{id}", response_model=CalendarResponse)
async def get_calendar_entry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single calendar entry with object authorization."""
    service = CalendarService(db)
    entry = service.get_entry_by_id(id, user=current_user)
    return _format_calendar_response(entry)


@calendar_router.patch("/{id}", response_model=CalendarResponse)
async def update_calendar_entry(
    id: uuid.UUID,
    data: CalendarUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates calendar entry with authorization verification."""
    service = CalendarService(db)
    entry = service.update_entry(id, data, actor_id=current_user.id)
    db.commit()
    refreshed = service.get_entry_by_id(entry.id)
    return _format_calendar_response(refreshed)


@calendar_router.delete("/{id}")
async def delete_calendar_entry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes calendar entry with authorization verification."""
    service = CalendarService(db)
    service.delete_entry(id, actor=current_user)
    db.commit()
    return {"success": True, "message": "Calendar entry deleted successfully"}


@calendar_router.post("/{id}/actions", response_model=CalendarResponse)
async def execute_calendar_action(
    id: uuid.UUID,
    payload: CalendarActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes manual calendar lifecycle actions:
    - 'mark_completed_for_me': Participant action; marks completion for current user only.
    - 'complete': Creator / authorized action; globally completes the activity.
    - 'in_progress': Creator / authorized action; marks activity in-progress.
    - 'cancel': Creator / authorized action; cancels the activity.
    """
    service = CalendarService(db)
    act = payload.action.strip().lower()
    if act == "mark_completed_for_me":
        res = service.mark_individual_completion(id, user=current_user)
    elif act == "complete":
        res = service.complete_entry(id, user=current_user, remarks=payload.remarks)
    elif act == "in_progress":
        res = service.set_in_progress(id, user=current_user, remarks=payload.remarks)
    elif act == "cancel":
        res = service.cancel_entry(id, user=current_user, reason=payload.remarks)
    else:
        raise ValidationException(
            f"Unsupported calendar action: '{payload.action}'. Supported: 'mark_completed_for_me', 'complete', 'in_progress', 'cancel'."
        )
    db.commit()
    return res


@calendar_router.post("/{id}/reschedule", response_model=CalendarResponse)
async def reschedule_calendar_entry(
    id: uuid.UUID,
    payload: CalendarRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reschedules a calendar activity.
    Saves original date, updates scheduled date & time, marks status RESCHEDULED,
    and alerts participants.
    """
    service = CalendarService(db)
    res = service.reschedule_entry(
        entry_id=id,
        user=current_user,
        new_date=payload.new_date,
        new_start_time=payload.new_start_time,
        new_end_time=payload.new_end_time,
        reason=payload.reason,
    )
    db.commit()
    return res
