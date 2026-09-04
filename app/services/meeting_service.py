from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import get_logger
from app.models.communication import NotificationType
from app.models.event import Event, EventTeamProfile
from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingParticipant,
    MeetingStatus,
    MeetingType,
    RSVPStatus,
)
from app.models.organization import Vertical
from app.models.rbac import Role, UserRole
from app.models.task import (
    Task,
    TaskHealth,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.user import AccountStatus, User
from app.schemas.meeting import (
    MeetingActionConvertToTaskRequest,
    MeetingActionItemCreate,
    MeetingCreate,
    MeetingParticipantCreate,
    MeetingParticipantUpdate,
    MeetingRequestCreate,
    MeetingRescheduleRequest,
    MeetingReviewRequest,
    MeetingRSVPRequest,
    MeetingUpdate,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


class MeetingService:
    """Manages operational meetings, request chains, participants, action items, and task conversion."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.notif_service = NotificationService(db)

    def create_meeting(self, data: MeetingCreate, organizer_id: UUID) -> Meeting:
        if data.vertical_id:
            vert = self.db.get(Vertical, data.vertical_id)
            if not vert:
                raise ValidationException("Target vertical division not found")

        if data.event_id:
            event = self.db.get(Event, data.event_id)
            if not event:
                raise ValidationException("Target event not found")

        meeting = Meeting(
            title=data.title,
            description=data.description,
            organizer_id=organizer_id,
            vertical_id=data.vertical_id,
            event_id=data.event_id,
            meeting_type=data.meeting_type,
            status=MeetingStatus.SCHEDULED,
            meeting_date=data.meeting_date,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location,
            meeting_url=data.meeting_url,
            remarks=data.remarks,
        )
        self.db.add(meeting)
        self.db.flush()

        # Add organizer as participant (Accepted by default)
        self.db.add(MeetingParticipant(
            meeting_id=meeting.id,
            user_id=organizer_id,
            rsvp_status=RSVPStatus.ACCEPTED,
            responded_at=datetime.now(timezone.utc),
            notes="Organizer",
        ))

        # Resolve group audience to active users
        resolved_p_ids = set(data.participant_ids or [])

        if data.include_all_organization:
            all_uids = self.db.scalars(
                select(User.id).where(User.account_status == AccountStatus.ACTIVE)
            ).all()
            resolved_p_ids.update(all_uids)

        if data.target_vertical_ids:
            from app.models.organization import UserVertical
            vert_uids = self.db.scalars(
                select(UserVertical.user_id)
                .join(User, UserVertical.user_id == User.id)
                .where(
                    UserVertical.vertical_id.in_(data.target_vertical_ids),
                    User.account_status == AccountStatus.ACTIVE,
                )
            ).all()
            resolved_p_ids.update(vert_uids)

        if data.target_roles:
            role_uids = self.db.scalars(
                select(UserRole.user_id)
                .join(Role, UserRole.role_id == Role.id)
                .join(User, UserRole.user_id == User.id)
                .where(
                    Role.name.in_(data.target_roles),
                    User.account_status == AccountStatus.ACTIVE,
                )
            ).all()
            resolved_p_ids.update(role_uids)

        if data.target_role_vertical_pairs:
            from app.models.organization import UserVertical
            for pair in data.target_role_vertical_pairs:
                r_name = pair.get("role")
                v_id = pair.get("vertical_id")
                if r_name and v_id:
                    pair_uids = self.db.scalars(
                        select(UserVertical.user_id)
                        .join(User, UserVertical.user_id == User.id)
                        .join(UserRole, User.id == UserRole.user_id)
                        .join(Role, UserRole.role_id == Role.id)
                        .where(
                            UserVertical.vertical_id == v_id,
                            Role.name == r_name,
                            User.account_status == AccountStatus.ACTIVE,
                        )
                    ).all()
                    resolved_p_ids.update(pair_uids)

        # Add invited participants and dispatch notifications
        invited_ids = []
        for p_id in resolved_p_ids:
            if p_id != organizer_id:
                u = self.db.get(User, p_id)
                if u and u.account_status == AccountStatus.ACTIVE:
                    self.db.add(MeetingParticipant(
                        meeting_id=meeting.id,
                        user_id=p_id,
                        rsvp_status=RSVPStatus.PENDING,
                    ))
                    invited_ids.append(p_id)

        if invited_ids:
            self.notif_service.create_batch_notifications(
                recipient_ids=invited_ids,
                title=f"Meeting Invitation: {meeting.title}",
                message=f"You have been invited to meeting '{meeting.title}' on {meeting.meeting_date}.",
                notification_type=NotificationType.MEETING,
                related_resource_type="MEETING",
                related_resource_id=meeting.id,
                exclude_user_id=organizer_id,
            )


        self.audit.log(
            action="MEETING_CREATE",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=organizer_id,
            details={
                "title": meeting.title,
                "meeting_date": meeting.meeting_date.isoformat(),
                "meeting_type": meeting.meeting_type.value,
            },
        )
        logger.info(f"Created Meeting '{meeting.title}' (id={meeting.id})")
        return meeting

    def request_meeting(
        self,
        data: MeetingRequestCreate,
        requester_id: UUID,
        current_user: Optional[User] = None,
    ) -> Meeting:
        """
        Submits a formal meeting request for approval.
        If requested by an EVENT_TEAM account, routes to the associated Event's Head POC.
        """
        # Determine caller roles
        roles = [r.name for r in current_user.roles] if current_user and hasattr(current_user, "roles") and current_user.roles else []
        if not roles and current_user:
            roles = [
                r.name
                for r in self.db.scalars(
                    select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == requester_id)
                ).all()
            ]

        is_event_team = "EVENT_TEAM" in roles and "ADMIN" not in roles and "SPORTS_CORE" not in roles

        if is_event_team:
            profile = self.db.scalar(select(EventTeamProfile).where(EventTeamProfile.user_id == requester_id))
            if not profile:
                raise ValidationException("Event Team profile not found for authenticated account")

            target_event = self.db.get(Event, profile.event_id)
            if not target_event:
                raise ValidationException("Associated event not found")

            target_event_id = target_event.id
            vertical_id = target_event.vertical_id
            organizer_id = target_event.primary_poc_id or requester_id
            meeting_type = MeetingType.EVENT_TEAM_SYNC
        else:
            target_event_id = data.event_id
            vertical_id = data.vertical_id
            organizer_id = requester_id
            meeting_type = MeetingType.INTERNAL_SYNC

        meeting = Meeting(
            title=data.title,
            description=data.description,
            organizer_id=organizer_id,
            vertical_id=vertical_id,
            event_id=target_event_id,
            meeting_type=meeting_type,
            status=MeetingStatus.REQUESTED,
            is_requested=True,
            requested_by_id=requester_id,
            meeting_date=data.meeting_date,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location,
            meeting_url=data.meeting_url,
            remarks=data.remarks,
        )
        self.db.add(meeting)
        self.db.flush()

        # Add requester as participant
        self.db.add(MeetingParticipant(
            meeting_id=meeting.id,
            user_id=requester_id,
            rsvp_status=RSVPStatus.PENDING,
            notes="Requester",
        ))

        # Add organizer/Head POC as participant if distinct
        if organizer_id != requester_id:
            self.db.add(MeetingParticipant(
                meeting_id=meeting.id,
                user_id=organizer_id,
                rsvp_status=RSVPStatus.PENDING,
                notes="Organizer / Head POC",
            ))
            # Attention notification to Head POC / organizer
            self.notif_service.create_notification(
                recipient_id=organizer_id,
                notification_type=NotificationType.MEETING,
                title=f"Meeting Request Received: {meeting.title}",
                message=f"A meeting request '{meeting.title}' was submitted for {meeting.meeting_date}.",
                related_resource_type="MEETING",
                related_resource_id=meeting.id,
            )

        # Add other invited participants
        for p_id in set(data.participant_ids):
            if p_id not in [requester_id, organizer_id]:
                u = self.db.get(User, p_id)
                if u and u.account_status == AccountStatus.ACTIVE:
                    self.db.add(MeetingParticipant(
                        meeting_id=meeting.id,
                        user_id=p_id,
                        rsvp_status=RSVPStatus.PENDING,
                    ))

        self.audit.log(
            action="MEETING_REQUEST",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=requester_id,
            details={
                "title": meeting.title,
                "requested_by_id": str(requester_id),
                "is_event_team": is_event_team,
            },
        )
        logger.info(f"Submitted Meeting Request '{meeting.title}' (id={meeting.id})")
        return meeting

    def review_meeting_request(
        self,
        meeting_id: UUID,
        data: MeetingReviewRequest,
        reviewer_id: UUID,
    ) -> Meeting:
        meeting = self.get_meeting_by_id(meeting_id)
        if meeting.status != MeetingStatus.REQUESTED:
            raise ValidationException(f"Cannot review meeting in status '{meeting.status.value}'. Must be 'REQUESTED'")

        # Four-eyes review: Author cannot approve their own meeting request
        if meeting.requested_by_id == reviewer_id:
            raise ForbiddenException("Self-review violation: Requester cannot review or approve their own meeting request")

        meeting.status = data.status

        if data.status == MeetingStatus.SCHEDULED:
            # Set organizer RSVP to ACCEPTED
            for p in meeting.participants:
                if p.user_id == reviewer_id:
                    p.rsvp_status = RSVPStatus.ACCEPTED
                    p.responded_at = datetime.now(timezone.utc)

            # Notify requester and all participants
            notify_users = {p.user_id for p in meeting.participants}
            if meeting.requested_by_id:
                notify_users.add(meeting.requested_by_id)

            for uid in notify_users:
                if uid != reviewer_id:
                    self.notif_service.create_notification(
                        recipient_id=uid,
                        notification_type=NotificationType.MEETING,
                        title=f"Meeting Request Approved: {meeting.title}",
                        message=f"The meeting '{meeting.title}' has been approved and scheduled for {meeting.meeting_date}.",
                        related_resource_type="MEETING",
                        related_resource_id=meeting.id,
                    )
        elif data.status == MeetingStatus.REJECTED:
            if data.remarks:
                meeting.remarks = f"{meeting.remarks or ''}\n[REJECTED]: {data.remarks}".strip()

            if meeting.requested_by_id and meeting.requested_by_id != reviewer_id:
                self.notif_service.create_notification(
                    recipient_id=meeting.requested_by_id,
                    notification_type=NotificationType.MEETING,
                    title=f"Meeting Request Rejected: {meeting.title}",
                    message=f"Your meeting request '{meeting.title}' was rejected. Remarks: {data.remarks or 'N/A'}",
                    related_resource_type="MEETING",
                    related_resource_id=meeting.id,
                )


        self.audit.log(
            action="MEETING_REVIEW_REQUEST",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=reviewer_id,
            details={"status": meeting.status.value, "remarks": data.remarks},
        )
        logger.info(f"Reviewed Meeting Request '{meeting.title}' -> {meeting.status.value}")
        return meeting

    def get_meeting_by_id(self, meeting_id: UUID, current_user: Optional[User] = None) -> Meeting:
        meeting = self.db.scalar(
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(
                selectinload(Meeting.organizer),
                selectinload(Meeting.vertical),
                selectinload(Meeting.event),
                selectinload(Meeting.participants).selectinload(MeetingParticipant.user),
                selectinload(Meeting.action_items).selectinload(MeetingActionItem.assignee),
            )
        )
        if not meeting:
            raise EntityNotFoundException(f"Meeting with ID '{meeting_id}' not found")

        if current_user:
            from app.services.authority_service import AuthorityService
            auth_service = AuthorityService(self.db)
            if not auth_service.can_access_object(current_user, "meeting", meeting):
                raise ForbiddenException("You do not have authorization to access this meeting")

        return meeting

    def list_meetings(
        self,
        vertical_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        meeting_type: Optional[MeetingType] = None,
        status: Optional[MeetingStatus] = None,
        user_id: Optional[UUID] = None,
        current_user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Meeting], int]:
        stmt = select(Meeting).options(
            selectinload(Meeting.organizer),
            selectinload(Meeting.vertical),
            selectinload(Meeting.event),
            selectinload(Meeting.participants).selectinload(MeetingParticipant.user),
            selectinload(Meeting.action_items).selectinload(MeetingActionItem.assignee),
        )
        count_stmt = select(func.count(Meeting.id))

        if current_user:
            from app.services.authority_service import AuthorityService
            from sqlalchemy import or_

            auth_service = AuthorityService(self.db)
            if not auth_service.is_executive_or_admin(current_user.id):
                user_roles = auth_service.get_user_role_names(current_user.id)
                user_event_ids = auth_service.get_user_event_ids(current_user.id)
                user_vids = auth_service.get_user_vertical_ids(current_user.id)

                part_meeting_ids = list(
                    self.db.scalars(
                        select(MeetingParticipant.meeting_id).where(MeetingParticipant.user_id == current_user.id)
                    ).all()
                )

                scope_conditions = []
                if user_vids:
                    scope_conditions.append(Meeting.vertical_id.in_(user_vids))
                if user_event_ids:
                    scope_conditions.append(Meeting.event_id.in_(user_event_ids))
                if part_meeting_ids:
                    scope_conditions.append(Meeting.id.in_(part_meeting_ids))
                scope_conditions.append(Meeting.organizer_id == current_user.id)
                scope_conditions.append(Meeting.requested_by_id == current_user.id)

                if scope_conditions:
                    stmt = stmt.where(or_(*scope_conditions))
                    count_stmt = count_stmt.where(or_(*scope_conditions))
                else:
                    return [], 0

        if vertical_id:
            stmt = stmt.where(Meeting.vertical_id == vertical_id)
            count_stmt = count_stmt.where(Meeting.vertical_id == vertical_id)
        if event_id:
            stmt = stmt.where(Meeting.event_id == event_id)
            count_stmt = count_stmt.where(Meeting.event_id == event_id)
        if meeting_type:
            stmt = stmt.where(Meeting.meeting_type == meeting_type)
            count_stmt = count_stmt.where(Meeting.meeting_type == meeting_type)
        if status:
            stmt = stmt.where(Meeting.status == status)
            count_stmt = count_stmt.where(Meeting.status == status)
        if user_id:
            stmt = stmt.join(MeetingParticipant, MeetingParticipant.meeting_id == Meeting.id).where(MeetingParticipant.user_id == user_id)
            count_stmt = count_stmt.join(MeetingParticipant, MeetingParticipant.meeting_id == Meeting.id).where(MeetingParticipant.user_id == user_id)

        total = self.db.scalar(count_stmt) or 0
        meetings = list(self.db.scalars(stmt.order_by(Meeting.meeting_date.desc()).offset(offset).limit(limit)).all())
        return meetings, total


    def update_meeting(self, meeting_id: UUID, data: MeetingUpdate, actor_id: UUID) -> Meeting:
        meeting = self.get_meeting_by_id(meeting_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(meeting, key, value)

        self.audit.log(
            action="MEETING_UPDATE",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details=update_data,
        )
        return meeting

    def reschedule_meeting(self, meeting_id: UUID, data: MeetingRescheduleRequest, actor_id: UUID) -> Meeting:
        meeting = self.get_meeting_by_id(meeting_id)
        old_date = meeting.meeting_date
        old_start = meeting.start_time

        meeting.meeting_date = data.meeting_date
        meeting.start_time = data.start_time
        meeting.end_time = data.end_time
        if data.location:
            meeting.location = data.location
        if data.remarks:
            meeting.remarks = f"{meeting.remarks or ''}\n[Rescheduled from {old_date} {old_start}]: {data.remarks}".strip()

        # Reset participant RSVPs to PENDING except organizer
        for p in meeting.participants:
            if p.user_id != meeting.organizer_id:
                p.rsvp_status = RSVPStatus.PENDING
                p.responded_at = None

            # Notification to participant
            if p.user_id != actor_id:
                self.notif_service.create_notification(
                    recipient_id=p.user_id,
                    notification_type=NotificationType.MEETING,
                    title=f"Meeting Rescheduled: {meeting.title}",
                    message=f"Meeting '{meeting.title}' has been rescheduled to {meeting.meeting_date} {meeting.start_time or ''}.",
                    related_resource_type="MEETING",
                    related_resource_id=meeting.id,
                )

        self.audit.log(
            action="MEETING_RESCHEDULE",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "old_date": old_date.isoformat(),
                "new_date": data.meeting_date.isoformat(),
                "remarks": data.remarks,
            },
        )
        return meeting

    def cancel_meeting(self, meeting_id: UUID, remarks: Optional[str], actor_id: UUID) -> Meeting:
        meeting = self.get_meeting_by_id(meeting_id)
        meeting.status = MeetingStatus.CANCELLED
        if remarks:
            meeting.remarks = f"{meeting.remarks or ''}\n[CANCELLED]: {remarks}".strip()

        # Notification to participants
        for p in meeting.participants:
            if p.user_id != actor_id:
                self.notif_service.create_notification(
                    recipient_id=p.user_id,
                    notification_type=NotificationType.MEETING,
                    title=f"Meeting Cancelled: {meeting.title}",
                    message=f"Meeting '{meeting.title}' scheduled for {meeting.meeting_date} has been cancelled.",
                    related_resource_type="MEETING",
                    related_resource_id=meeting.id,
                )

        self.audit.log(
            action="MEETING_CANCEL",
            resource_type="MEETING",
            resource_id=str(meeting.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"remarks": remarks},
        )
        return meeting

    def add_participant(self, meeting_id: UUID, data: MeetingParticipantCreate, actor_id: UUID) -> MeetingParticipant:
        meeting = self.get_meeting_by_id(meeting_id)
        target_u = self.db.get(User, data.user_id)
        if not target_u or target_u.account_status != AccountStatus.ACTIVE:
            raise ValidationException("Participant user must exist and have ACTIVE status")

        existing = self.db.scalar(
            select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id, MeetingParticipant.user_id == data.user_id)
        )
        if existing:
            existing.notes = data.notes
            participant = existing
        else:
            participant = MeetingParticipant(
                meeting_id=meeting.id,
                user_id=data.user_id,
                rsvp_status=RSVPStatus.PENDING,
                notes=data.notes,
            )
            self.db.add(participant)

            if data.user_id != actor_id:
                self.notif_service.create_notification(
                    recipient_id=data.user_id,
                    notification_type=NotificationType.MEETING,
                    title=f"Meeting Invitation: {meeting.title}",
                    message=f"You have been added as a participant for meeting '{meeting.title}' on {meeting.meeting_date}.",
                    related_resource_type="MEETING",
                    related_resource_id=meeting.id,
                )

        self.db.flush()
        self.audit.log(
            action="MEETING_PARTICIPANT_ADD",
            resource_type="MEETING_PARTICIPANT",
            resource_id=str(participant.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"meeting_id": str(meeting.id), "user_id": str(data.user_id)},
        )
        return participant

    def update_participant(self, meeting_id: UUID, user_id: UUID, data: MeetingParticipantUpdate, actor_id: UUID) -> MeetingParticipant:
        meeting = self.get_meeting_by_id(meeting_id)
        participant = self.db.scalar(
            select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id, MeetingParticipant.user_id == user_id)
        )
        if not participant:
            raise EntityNotFoundException("MeetingParticipant", f"{meeting_id}:{user_id}")

        if data.notes is not None:
            participant.notes = data.notes

        self.db.flush()
        self.audit.log(
            action="MEETING_UPDATE_PARTICIPANT",
            resource_type="MEETING_PARTICIPANT",
            resource_id=str(participant.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"meeting_id": str(meeting.id), "user_id": str(user_id)},
        )
        return participant

    def remove_participant(self, meeting_id: UUID, user_id: UUID, actor_id: UUID) -> None:
        meeting = self.get_meeting_by_id(meeting_id)
        if user_id == meeting.organizer_id:
            raise ValidationException("Cannot remove the meeting organizer from participants")

        participant = self.db.scalar(
            select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id, MeetingParticipant.user_id == user_id)
        )
        if not participant:
            raise EntityNotFoundException("MeetingParticipant", f"{meeting_id}:{user_id}")

        self.db.delete(participant)
        self.db.flush()
        self.audit.log(
            action="MEETING_REMOVE_PARTICIPANT",
            resource_type="MEETING_PARTICIPANT",
            resource_id=str(participant.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={"meeting_id": str(meeting.id), "user_id": str(user_id)},
        )

    def update_rsvp(self, meeting_id: UUID, user_id: UUID, data: MeetingRSVPRequest) -> MeetingParticipant:
        participant = self.db.scalar(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.user_id == user_id,
            )
        )
        if not participant:
            raise EntityNotFoundException("You are not listed as a participant for this meeting")

        participant.rsvp_status = data.rsvp_status
        participant.responded_at = datetime.now(timezone.utc)
        if data.notes:
            participant.notes = data.notes

        self.audit.log(
            action="MEETING_RSVP",
            resource_type="MEETING_PARTICIPANT",
            resource_id=str(participant.id),
            outcome="SUCCESS",
            actor_id=user_id,
            details={"meeting_id": str(meeting_id), "rsvp_status": data.rsvp_status.value},
        )
        return participant

    # ==================== ACTION ITEMS & TASK CONVERSION ====================

    def create_action_item(
        self,
        meeting_id: UUID,
        data: MeetingActionItemCreate,
        actor_id: UUID,
    ) -> MeetingActionItem:
        meeting = self.get_meeting_by_id(meeting_id)

        if data.assignee_id:
            u = self.db.get(User, data.assignee_id)
            if not u or u.account_status != AccountStatus.ACTIVE:
                raise ValidationException("Assignee user not found or is inactive")

        action_item = MeetingActionItem(
            meeting_id=meeting.id,
            description=data.description,
            assignee_id=data.assignee_id,
            priority=data.priority,
            due_date=data.due_date,
        )
        self.db.add(action_item)
        self.db.flush()

        self.audit.log(
            action="MEETING_ACTION_ITEM_CREATE",
            resource_type="MEETING_ACTION_ITEM",
            resource_id=str(action_item.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "meeting_id": str(meeting.id),
                "description": action_item.description[:100],
            },
        )
        return action_item

    def convert_action_item_to_task(
        self,
        meeting_id: UUID,
        item_id: UUID,
        data: MeetingActionConvertToTaskRequest,
        actor_id: UUID,
    ) -> Tuple[MeetingActionItem, Task]:
        meeting = self.get_meeting_by_id(meeting_id)

        stmt = select(MeetingActionItem).where(
            MeetingActionItem.id == item_id,
            MeetingActionItem.meeting_id == meeting.id,
        )
        item = self.db.scalar(stmt)
        if not item:
            raise EntityNotFoundException(f"Meeting action item with ID '{item_id}' not found")

        # Duplicate conversion prevention
        if item.is_converted or item.converted_task_id:
            raise ValidationException("This meeting action item has already been converted to a Master Task")

        target_vertical_id = data.vertical_id or meeting.vertical_id
        if not target_vertical_id:
            raise ValidationException("A target vertical division is required to create a Master Task")

        target_assignee_id = data.assigned_to_id or item.assignee_id
        if not target_assignee_id:
            raise ValidationException("An assigned user is required to create a Master Task")

        assignee = self.db.get(User, target_assignee_id)
        if not assignee or assignee.account_status != AccountStatus.ACTIVE:
            raise ValidationException("Assignee user is invalid or inactive")

        task_title = data.title or (item.description[:250] if len(item.description) <= 250 else item.description[:247] + "...")
        task_priority = data.priority or item.priority
        task_deadline = data.deadline or item.due_date

        # Instantiate Master Task with meeting, event, and vertical context
        task = Task(
            title=task_title,
            description=f"[Meeting Action Item from: {meeting.title}]\n{item.description}",
            vertical_id=target_vertical_id,
            assigned_to_id=target_assignee_id,
            assigned_by_id=actor_id,
            priority=task_priority,
            deadline=task_deadline,
            event_id=meeting.event_id,
            meeting_id=meeting.id,
            status=TaskStatus.NOT_STARTED,
            health=TaskHealth.ON_TRACK,
            completion_percentage=0,
            task_type=TaskType.MEETING_FOLLOW_UP,
        )
        self.db.add(task)
        self.db.flush()

        # Update action item conversion status
        item.is_converted = True
        item.converted_task_id = task.id
        item.converted_at = datetime.now(timezone.utc)
        item.converted_by_id = actor_id
        self.db.flush()

        # Dispatch notification to assignee
        if target_assignee_id and target_assignee_id != actor_id:
            self.notif_service.create_notification(
                recipient_id=target_assignee_id,
                notification_type=NotificationType.TASK,
                title=f"New Task from Meeting: {task.title}",
                message=f"You have been assigned task '{task.title}' originating from meeting '{meeting.title}'.",
                related_resource_type="TASK",
                related_resource_id=task.id,
            )


        self.audit.log(
            action="MEETING_ACTION_CONVERT_TO_TASK",
            resource_type="MEETING_ACTION_ITEM",
            resource_id=str(item.id),
            outcome="SUCCESS",
            actor_id=actor_id,
            details={
                "meeting_id": str(meeting.id),
                "created_task_id": str(task.id),
                "task_title": task.title,
            },
        )
        logger.info(f"Converted MeetingActionItem '{item.id}' to Task '{task.id}'")
        return item, task
