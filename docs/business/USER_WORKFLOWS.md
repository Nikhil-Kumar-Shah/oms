# End-to-End Operational User Workflows
**Paradox Sports Operations Management System (OMS)**

This document details the step-by-step procedural journeys for real-world operations in Paradox Sports OMS.

---

## Journey 1: User Onboarding & Vertical Assignment
1. **Administrator Creation**: `ADMIN` logs in and navigates to User Management (`POST /api/v1/admin/users`).
2. **Identity Creation**: Admin provides username, full name, email, and temporary password. Account status initializes to `ACTIVE`.
3. **Role Assignment**: Admin assigns one or more canonical roles (e.g. `COORDINATOR`, `VOLUNTEER`).
4. **Vertical Assignment**: Admin assigns user to their primary operational vertical division (e.g. `Football Operations`).
5. **Initial Login**: User logs in with temporary credentials, changes password (`POST /api/v1/auth/change-password`), and acquires a session cookie/token.
6. **Profile Confirmation**: User verifies profile and effective permissions via `GET /api/v1/auth/me`.

---

## Journey 2: Task Assignment, Execution, Blocker Escalation & Completion
1. **Task Creation**: Coordinator creates a master task (`POST /api/v1/tasks`) with `title`, `description`, `vertical_id`, `deadline`, and `priority`. Status initializes to `NOT_STARTED`.
2. **Assignment**: Coordinator assigns task to an active volunteer in the vertical (`assigned_to_id`).
3. **Notification**: Assignee receives an automated attention notification (`NotificationType.TASK`).
4. **My Work Intake**: Task appears immediately on the assignee's personal workspace (`GET /api/v1/my-work`).
5. **Progress Update**: Assignee starts work, transitions status to `IN_PROGRESS` (`POST /api/v1/tasks/{id}/transition`), and sets `completion_percentage: 30`.
6. **Blocker Declared**: An unexpected obstacle arises (e.g. equipment missing). Assignee transitions status to `BLOCKED` with mandatory `blocker_reason`.
7. **Coordinator Alert**: Task health changes to `BLOCKED`. Coordinator receives an alert and reviews blocker notes.
8. **Blocker Resolution**: Coordinator provides assistance, resolves blocker, and transitions task back to `IN_PROGRESS`.
9. **Task Completion**: Assignee finishes work, posts final completion notes, and transitions status to `COMPLETED` (`completion_percentage: 100`).
10. **Audit Record**: Immutable audit entry `TASK_TRANSITION` is logged in PostgreSQL.

---

## Journey 3: Cross-Vertical Requirement Routing
1. **Requirement Raised**: Football Operations needs 4 goal net sets from Logistics. Coordinator raises requirement (`POST /api/v1/requirements`) with `requesting_vertical_id: Football`, `target_vertical_id: Logistics`, and `priority: HIGH`. Status initializes to `OPEN`.
2. **Target Queue Intake**: Requirement appears in Logistics Coordinator's incoming queue (`GET /api/v1/requirements?target_vertical_id=...`).
3. **Assignment**: Logistics Coordinator assigns requirement to an inventory team member. Status transitions to `ASSIGNED`.
4. **Operational Messaging**: Requester and Assignee exchange coordination updates via threaded messages (`POST /api/v1/requirements/{id}/messages`).
5. **Fulfillment & Sign-off**: Logistics team delivers nets and marks requirement `COMPLETED`. Both vertical coordinators receive resolution notifications.

---

## Journey 4: Daily Work Reporting & Supervisor Review
1. **End-of-Day Submission**: Volunteer opens Daily Reporting (`GET /dev/reports` or `POST /api/v1/reports`).
2. **Drafting / Submitting**: User fills `work_summary`, `tasks_completed`, `blockers`, `issues`, and `next_actions`. User clicks "Submit Report" (`status: SUBMITTED`).
3. **Supervisor Notification**: Vertical Coordinator receives notice of submitted daily report.
4. **Supervisor Review**: Coordinator opens report (`GET /api/v1/reports/{id}`).
5. **Self-Review Prevention**: If Coordinator accidentally attempts to review their own personal report, the system rejects the action with `HTTP 403 Forbidden` (`Self-review violation`).
6. **Approval & Feedback**: Coordinator reviews team member's report, provides comments, and transitions status to `REVIEWED` (or `FLAGGED` / `RETURNED` if incomplete).

---

## Journey 5: Directive Issuance & Compliance Acknowledgment
1. **Directive Drafted**: Sports Core executive drafts a binding operational directive (`POST /api/v1/directives`) with `DirectiveScope.ALL` or `DirectiveScope.VERTICAL`.
2. **Issuance**: Executive issues directive (`POST /api/v1/directives/{id}/issue`). Status becomes `ISSUED`.
3. **Roster Generation**: System automatically generates individual acknowledgement rows for all target vertical members (`DirectiveAcknowledgement` with `status: PENDING`).
4. **Member Notification**: High-priority alert sent to all recipient attention feeds.
5. **Sign-off**: Members view directive content and submit formal acknowledgement (`POST /api/v1/directives/{id}/acknowledge`). Status updates to `ACKNOWLEDGED`.
6. **Compliance Dashboard**: Leadership monitors live acknowledgement percentages in real time (`GET /api/v1/directives/{id}`).

---

## Journey 6: Resource Ownership Transfer
1. **Initiation**: Outgoing Event Head initiates transfer of an Event to an incoming Coordinator (`POST /api/v1/transfers`) with `TransferResourceType.EVENT`, `resource_id`, `requested_owner_id`, and `reason`.
2. **Status**: Transfer initializes to `PENDING`.
3. **Target Alert**: Incoming Coordinator receives transfer request notification.
4. **Review & Sign-off**: Incoming Coordinator or Sports Core reviews request (`POST /api/v1/transfers/{id}/review`).
5. **Self-Approval Prevention**: Requester cannot approve their own transfer request.
6. **Atomic Reassignment**: Upon approval (`status: APPROVED`), the service atomically updates `event.event_head_id` in PostgreSQL and logs an audit record.
