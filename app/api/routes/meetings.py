"""
Meetings Management API Endpoints
Paradox Sports OMS - Phase 4 Operational Systems & Governance
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, require_permissions, require_user_session
from app.models.meeting import Meeting, MeetingActionItem, MeetingParticipant, MeetingStatus, MeetingType
from app.models.user import User
from app.schemas.meeting import (
    MeetingActionConvertToTaskRequest,
    MeetingActionItemCreate,
    MeetingActionItemResponse,
    MeetingCreate,
    MeetingListResponse,
    MeetingParticipantCreate,
    MeetingParticipantResponse,
    MeetingRequestCreate,
    MeetingRescheduleRequest,
    MeetingResponse,
    MeetingReviewRequest,
    MeetingRSVPRequest,
    MeetingUpdate,
)
from app.schemas.task import TaskResponse
from app.services.meeting_service import MeetingService

router = APIRouter(prefix="/meetings", tags=["Meetings Management"])


def _format_participant_response(p: MeetingParticipant) -> MeetingParticipantResponse:
    return MeetingParticipantResponse(
        id=p.id,
        meeting_id=p.meeting_id,
        user_id=p.user_id,
        username=p.user.username if p.user else None,
        full_name=p.user.full_name if p.user else None,
        rsvp_status=p.rsvp_status,
        invited_at=p.invited_at,
        responded_at=p.responded_at,
        notes=p.notes,
    )


def _format_action_item_response(item: MeetingActionItem) -> MeetingActionItemResponse:
    return MeetingActionItemResponse(
        id=item.id,
        meeting_id=item.meeting_id,
        description=item.description,
        assignee_id=item.assignee_id,
        assignee_full_name=item.assignee.full_name if item.assignee else None,
        assignee_username=item.assignee.username if item.assignee else None,
        priority=item.priority,
        due_date=item.due_date,
        is_converted=item.is_converted,
        converted_task_id=item.converted_task_id,
        converted_at=item.converted_at,
        converted_by_id=item.converted_by_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _format_task_response(task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        vertical_id=task.vertical_id,
        vertical_name=task.vertical.name if task.vertical else None,
        assigned_to_id=task.assigned_to_id,
        assigned_to_username=task.assigned_to.username if task.assigned_to else None,
        assigned_to_name=task.assigned_to.full_name if task.assigned_to else None,
        assigned_by_id=task.assigned_by_id,
        assigned_by_username=task.assigned_by.username if task.assigned_by else None,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        priority=task.priority,
        status=task.status,
        completion_percentage=task.completion_percentage,
        health=task.health,
        date_assigned=task.date_assigned,
        deadline=task.deadline,
        completed_on=task.completed_on,
        blockers=task.blockers,
        remarks=task.remarks,
        latest_update=task.latest_update,
        evidence_link=task.evidence_link,
        deficiency=task.deficiency,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _format_meeting_response(meeting: Meeting) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        meeting_type=meeting.meeting_type,
        meeting_date=meeting.meeting_date,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        location=meeting.location,
        meeting_url=meeting.meeting_url,
        remarks=meeting.remarks,
        organizer_id=meeting.organizer_id,
        organizer_username=meeting.organizer.username if meeting.organizer else None,
        vertical_id=meeting.vertical_id,
        vertical_name=meeting.vertical.name if meeting.vertical else None,
        event_id=meeting.event_id,
        event_name=meeting.event.name if meeting.event else None,
        status=meeting.status,
        is_requested=meeting.is_requested or False,
        requested_by_id=meeting.requested_by_id,
        requested_by_username=meeting.requested_by.username if getattr(meeting, "requested_by", None) else None,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        participants=[_format_participant_response(p) for p in meeting.participants],
        action_items=[_format_action_item_response(a) for a in meeting.action_items],
    )


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["meetings.create"]))])
def create_meeting(
    data: MeetingCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.create_meeting(data, organizer_id=current_user.id)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.post("/request", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["meetings.create"]))])
def request_meeting(
    data: MeetingRequestCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.request_meeting(data, requester_id=current_user.id, current_user=current_user)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.post("/{meeting_id}/review-request", response_model=MeetingResponse, dependencies=[Depends(require_permissions(["meetings.update"]))])
def review_meeting_request(
    meeting_id: UUID,
    data: MeetingReviewRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.review_meeting_request(meeting_id, data, reviewer_id=current_user.id)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.get("", response_model=MeetingListResponse, dependencies=[Depends(require_permissions(["meetings.read"]))])
def list_meetings(
    vertical_id: Optional[UUID] = Query(None),
    event_id: Optional[UUID] = Query(None),
    meeting_type: Optional[MeetingType] = Query(None),
    meeting_status: Optional[MeetingStatus] = Query(None, alias="status"),
    user_id: Optional[UUID] = Query(None, description="Filter by participant/organizer"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    items, total = service.list_meetings(
        vertical_id=vertical_id,
        event_id=event_id,
        meeting_type=meeting_type,
        status=meeting_status,
        user_id=user_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    return MeetingListResponse(
        items=[_format_meeting_response(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse, dependencies=[Depends(require_permissions(["meetings.read"]))])
def get_meeting(
    meeting_id: UUID,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.get_meeting_by_id(meeting_id, current_user=current_user)
    return _format_meeting_response(meeting)



@router.put("/{meeting_id}", response_model=MeetingResponse, dependencies=[Depends(require_permissions(["meetings.update"]))])
def update_meeting(
    meeting_id: UUID,
    data: MeetingUpdate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.update_meeting(meeting_id, data, actor_id=current_user.id)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.post("/{meeting_id}/reschedule", response_model=MeetingResponse, dependencies=[Depends(require_permissions(["meetings.update"]))])
def reschedule_meeting(
    meeting_id: UUID,
    data: MeetingRescheduleRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.reschedule_meeting(meeting_id, data, actor_id=current_user.id)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.post("/{meeting_id}/cancel", response_model=MeetingResponse, dependencies=[Depends(require_permissions(["meetings.update"]))])
def cancel_meeting(
    meeting_id: UUID,
    remarks: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    meeting = service.cancel_meeting(meeting_id, remarks=remarks, actor_id=current_user.id)
    db.commit()
    return _format_meeting_response(service.get_meeting_by_id(meeting.id))


@router.post("/{meeting_id}/participants", response_model=MeetingParticipantResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["meetings.update"]))])
def add_participant(
    meeting_id: UUID,
    data: MeetingParticipantCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    p = service.add_participant(meeting_id, data, actor_id=current_user.id)
    db.commit()
    return _format_participant_response(p)


@router.post("/{meeting_id}/rsvp", response_model=MeetingParticipantResponse, dependencies=[Depends(require_permissions(["meetings.rsvp"]))])
def rsvp_meeting(
    meeting_id: UUID,
    data: MeetingRSVPRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    p = service.update_rsvp(meeting_id, current_user.id, data)
    db.commit()
    return _format_participant_response(p)


# ==================== ACTION ITEMS & TASK CONVERSION ENDPOINTS ====================

@router.post("/{meeting_id}/action-items", response_model=MeetingActionItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["meetings.update"]))])
def create_action_item(
    meeting_id: UUID,
    data: MeetingActionItemCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = MeetingService(db)
    item = service.create_action_item(meeting_id, data, actor_id=current_user.id)
    db.commit()
    db.refresh(item)
    return _format_action_item_response(item)


@router.post("/{meeting_id}/action-items/{item_id}/convert-to-task", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["tasks.create"]))])
def convert_action_item_to_task(
    meeting_id: UUID,
    item_id: UUID,
    data: MeetingActionConvertToTaskRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    meeting_service = MeetingService(db)
    action_item, task = meeting_service.convert_action_item_to_task(
        meeting_id=meeting_id,
        item_id=item_id,
        data=data,
        actor_id=current_user.id,
    )
    db.commit()
    db.refresh(task)
    return _format_task_response(task)
