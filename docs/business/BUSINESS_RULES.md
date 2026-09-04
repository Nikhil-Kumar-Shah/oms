# Business Rules & Operational Policies
**Paradox Sports Operations Management System (OMS)**

## 1. Executive Summary & Architectural Invariants

The Paradox Sports Operations Management System (OMS) is a server-authoritative operational platform.
- **Authoritative Database**: PostgreSQL is the single authoritative source of truth.
- **Organizational Hierarchy**: `Organization -> Vertical -> User` (Strictly NO "Department" concept across any table, model, schema, API route, or UI view).
- **Canonical Roles**: `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`, `VOLUNTEER`, `EVENT_TEAM`.
- **Zero Hard-Deletion Policy**: Operational records are never hard-deleted via normal operational workflows; they transition through explicit terminal lifecycle states (`CANCELLED`, `CLOSED`, `ARCHIVED`, `REJECTED`).
- **Audit Immutability**: All authentication, administrative, and operational events are recorded in an append-only, immutable audit trail.

---

## 2. The Twenty Core Operational Business Rules

### Rule 1: Who Can Do What?
- **ADMIN**: Unrestricted system administration, organization configuration, role assignment, vertical management, and audit inspection.
- **SPORTS_CORE & DEPUTY_CORE**: Executive operational leadership with cross-vertical visibility, event sign-off authority, directive issuance, and report review.
- **SUPER_COORDINATOR**: Cross-vertical operational coordination, task creation, cross-vertical requirement routing, and meeting facilitation.
- **COORDINATOR**: Vertical-scoped operational management, task assignment, daily report review, event team coordination, and readiness updates.
- **VOLUNTEER & EVENT_TEAM**: Operational execution, task progress updates, checklist completion, daily work report submission, and requirement messaging.

### Rule 2: Who Can See What?
- **Organization & Verticals**: Visible to all active authenticated users.
- **Personal Work ("My Work")**: Strictly isolated to the authenticated user via server-side identity (`current_user.id`).
- **Vertical Tasks & Events**: Visible to users actively assigned to the vertical, plus leadership roles (`ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`).
- **Confidential Issues**: Restricted strictly to leadership roles or the explicit reporter and assignee.
- **Notifications**: Strictly isolated to the recipient user (IDOR protected).
- **Audit Logs & System Config**: Restricted strictly to `ADMIN` and executive leadership.

### Rule 3: Who Can Create What?
- **Verticals & User Accounts**: `ADMIN`.
- **Master Tasks**: `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`.
- **Operational Events**: `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `COORDINATOR`.
- **Cross-Vertical Requirements**: `ADMIN`, `SPORTS_CORE`, `COORDINATOR`, `SUPER_COORDINATOR`.
- **Issues**: All active users (`VOLUNTEER`, `EVENT_TEAM`, `COORDINATOR`, `ADMIN`).
- **Daily Work Reports**: All active users assigned to operational verticals.
- **Directives & Announcements**: `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE` (organization-wide), `COORDINATOR` (vertical-scoped).
- **Form Schemas**: `ADMIN`, `SPORTS_CORE`, `COORDINATOR`.

### Rule 4: Who Can Modify What?
- **Master Task Details**: Author or vertical coordinator. Assignee can only update status, progress percentage, blockers, and comments.
- **Event Parameters**: Event Head, Primary POC, Vertical Coordinator, or Sports Core.
- **Form Definitions**: Author or Admin while in `DRAFT` status. Published versions are immutable.
- **Directives & Announcements**: Author or Admin while in `DRAFT` status. Issued directives cannot be modified; they can only be superseded or cancelled.

### Rule 5: Who Can Assign Work?
- Task assignment requires `tasks.assign` permission within the target vertical.
- Assignees must be `ACTIVE` users actively assigned to the target vertical division.
- Cross-vertical task assignment is prohibited; cross-vertical work must be requested via the **Requirement Workflow**.

### Rule 6: Who Can Approve Work?
- **Daily Work Reports**: Vertical Supervisor, Coordinator, or Core Executive. Authors are strictly forbidden from approving their own reports (**Self-Review Prevention Rule**).
- **Ownership Transfers**: Resource supervisor or target owner. Requesters cannot approve their own requests (**Self-Approval Prevention Rule**).
- **Event Readiness Checkpoints**: Event Head, Designated POC, or Sports Core.
- **Form Submissions**: Form Reviewer, Vertical Coordinator, or Admin.

### Rule 7: Who Can Reject Work?
- **Daily Reports**: Reviewer can mark report as `RETURNED` or `FLAGGED` with mandatory feedback comments.
- **Ownership Transfers**: Reviewer can transition transfer request to `REJECTED` with remarks.
- **Requirements**: Target vertical coordinator can transition requirement to `REJECTED` if infeasible or misrouted.
- **Form Submissions**: Form reviewer can transition submission to `REJECTED` or `RETURNED` with review notes.

### Rule 8: Who Can Escalate an Issue?
- Any issue assignee, reporter, or vertical coordinator can transition an issue to `ESCALATED`.
- Escalated issues automatically notify Sports Core leadership and flag in executive attention feeds.

### Rule 9: What Happens When a User Becomes Inactive / Suspended?
- Account status transitions to `INACTIVE` or `SUSPENDED`.
- All active user sessions are immediately revoked in PostgreSQL (`UserSession.is_revoked = True`).
- Authentication endpoints reject subsequent login attempts (`HTTP 401/403`).
- Existing completed records (reports, tasks, comments) remain intact as immutable historical audit trails.
- Active task assignments remain attached to the user record but trigger visual reassignment warnings in supervisor boards.

### Rule 10: What Happens When a Vertical Is Disabled?
- Vertical status transitions to `DISABLED`.
- Creation of new tasks, events, forms, or directives for this vertical is blocked by service validation.
- Existing historical tasks, reports, and events remain read-only and queryable for audit and reporting.
- User vertical assignments remain recorded in database for historical continuity.

### Rule 11: What Happens When an Event Changes State?
- **PLANNING &rarr; IN_PROGRESS**: Triggers event execution phase; readiness checkpoints lock.
- **IN_PROGRESS &rarr; COMPLETED**: Finalizes event execution; creates completion audit record.
- **CANCELLED**: Marks event as aborted; preserves all team assignments and checkpoints for historical retrospective.
- **ARCHIVED**: Hides event from active operational views while preserving full database queryability.

### Rule 12: What Happens When a Task Becomes Blocked?
- Assignee transitions task status to `BLOCKED`.
- System requires a non-empty `blocker_reason`.
- Task health automatically updates to `BLOCKED` (`TaskHealth.BLOCKED`).
- Automated notification is dispatched to the task author and vertical coordinator.

### Rule 13: What Happens When a Requirement Is Submitted?
- Requesting vertical submits cross-vertical requirement with target vertical and priority.
- Status initializes to `OPEN`.
- Requirement is queued in target vertical coordinator's incoming requirements inbox.
- Automated notification dispatched to target vertical leadership.

### Rule 14: What Happens When a Meeting Is Cancelled?
- Organizer or Coordinator transitions meeting status to `CANCELLED`.
- System records cancellation reason.
- Automated notifications dispatched to all RSVP participants.
- Meeting calendar entry updates to cancelled state.

### Rule 15: What Happens When a Form Is Approved?
- Form submission status transitions from `UNDER_REVIEW` to `APPROVED`.
- If configured with an operational transformation rule, the service atomically creates the corresponding native OMS entity (`TASK`, `EVENT`, `REQUIREMENT`, `ISSUE`).
- Transformation record ID is linked to the submission metadata.

### Rule 16: What Happens When Ownership Changes?
- Requester initiates ownership transfer request (`OwnershipTransfer`).
- Transfer status initializes to `PENDING`.
- Designated reviewer approves request (self-approval blocked).
- Service atomically reassigns `created_by_id` or owner field on target entity and logs an audit record.

### Rule 17: What Records Are Permanent?
- **Audit Logs (`audit_logs`)**: Strictly immutable, append-only, permanent records.
- **User Sessions (`user_sessions`)**: Preserved for security forensics even after revocation.
- **Task Histories (`task_history`)**: Immutable log of all task field mutations.
- **Directives & Acknowledgment Rosters**: Permanent compliance records.

### Rule 18: What Records Can Be Archived?
- Tasks (`TaskStatus.ARCHIVED`), Events (`EventStatus.ARCHIVED`), Forms (`FormStatus.ARCHIVED`), Announcements (`AnnouncementStatus.ARCHIVED`), Verticals (`VerticalStatus.ARCHIVED`).
- Archival removes records from active operational feeds while preserving relational integrity in PostgreSQL.

### Rule 19: What Operations Generate Notifications?
- Task assignment & blocker declaration.
- Event team assignment & POC designation.
- Cross-vertical requirement submission & assignment.
- Meeting invitation & cancellation.
- Directive issuance requiring acknowledgement.
- Issue escalation.
- Ownership transfer request & review outcome.

### Rule 20: What Operations Generate Audit Records?
- User authentication (login success/failure, logout, password change).
- User lifecycle state mutations (creation, update, disabling, reactivation).
- Role assignment and permission override changes.
- Vertical creation, modification, and status transitions.
- Master task creation, assignment, transition, and cancellation.
- Event creation, POC assignment, and status transitions.
- Requirement creation, routing, and completion.
- Form publishing, submission review, and native transformation.
- Ownership transfer requests, approvals, and rejections.
- System configuration changes.
