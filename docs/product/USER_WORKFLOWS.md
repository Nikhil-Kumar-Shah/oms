# USER WORKFLOWS & ROLE JOURNEYS
## Paradox Sports Operations Management System (OMS)

**Document Status:** USER JOURNEY SPECIFICATION & PROCEDURAL FLOWS  
**Authoritative Stack:** FastAPI | SQLAlchemy 2.x | PostgreSQL 16+ | Pydantic v2 | Jinja2  
**Verification Date:** September 1, 2026  

---

## 1. Canonical Role Access & Operational Matrix

| Role | What They See | What They Create | What They Edit / Transition | What They Assign | What They Approve / Reject | What They Escalate | What They Can Archive | What They Cannot Access |
|---|---|---|---|---|---|---|---|---|
| **ADMIN** | Complete system state across all verticals, audit logs, configs | Users, Verticals, Roles, Forms, Directives, Announcements | All resources across entire organization | Roles, Verticals, Any Task/Event | All Form Submissions, Transfers, Reports | Direct access (Target of escalations) | All resources across system | None (Super-user) |
| **SPORTS_CORE** | All verticals, executive analytics, readiness dashboards | Events, Directives, Announcements, Master Calendar | Events, Directives, Calendar, Meetings | Event Heads, Multi-vertical Tasks | Cross-vertical requests, Event milestones | Direct access (Executive level) | Completed Events, Directives | System configs, raw RBAC role modifications |
| **DEPUTY_CORE** | All verticals, operational performance, issue register | Meetings, Directives, Announcements, Master Calendar | Events, Directives, Calendar, Issues | Operational Tasks within delegated scope | Submissions, Transfers within delegated scope | Escalates to Sports Core / Admin | Completed Meetings, Tasks | System security configs, audit log administration |
| **SUPER_COORDINATOR** | Assigned supervisory verticals, team performance | Tasks, Issues, Meetings, Requirements, Forms | Tasks, Meetings, Requirements within assigned verticals | Tasks to Coordinators / Volunteers | Daily Reports, Form Submissions in vertical | Escalates issues to Sports Core / Deputy | Completed Tasks, Closed Issues in vertical | Unassigned verticals, system admin endpoints |
| **COORDINATOR** | Assigned vertical records, team roster, event duties | Tasks, Issues, Daily Reports, Meetings, Requirements | Tasks, Issues, Meetings within own vertical | Tasks to Volunteers in own vertical | Daily Reports of Volunteers, Form Submissions | Escalates blockers & issues to Super Coordinator | Completed Tasks in own vertical | Other vertical records, confidential executive issues |
| **VOLUNTEER** | Own vertical tasks, My Work, public calendar & announcements | Daily Reports, Issues, Requirement messages | Own Task progress (0–100%), own Daily Reports (Draft) | None | None | Flags blockers & issues to Coordinator | None | Self-reviewing reports, editing tasks assigned to others |
| **EVENT_TEAM** | Assigned event details, event readiness, match schedule | Match updates, event-specific issues | Event checkpoint notes, assigned event task progress | None | None | Escalates match delays to Event Head | None | Vertical administrative settings, non-event tasks |

---

## 2. Step-by-Step Operational Journeys

### Journey 1: Admin Onboarding & Provisioning
```
[Admin Logs In]
       ↓
[Creates Vertical Division in 'verticals']
       ↓
[Creates User Account with Argon2id Password]
       ↓
[Assigns User to Vertical and Canonical Role]
       ↓
[User Logs In & Receives Scoped Session Token]
```
1. Admin navigates to `/admin/organization` and creates vertical division (e.g. `Aquatics Division`).
2. Admin provisions user account specifying email, username, and initial vertical link.
3. Admin assigns canonical role (e.g. `COORDINATOR`).
4. User logs in; server calculates effective permissions and filters UI exclusively to assigned vertical.

---

### Journey 2: User Starting Work ("My Work")
```
[User Authenticates]
       ↓
[Opens "My Work" Dashboard]
       ↓
[Views Assigned Tasks Sorted by Deadline]
       ↓
[Checks Pending Directive Acknowledgements & Meeting Invites]
```
1. User logs in and opens My Work (`/api/v1/tasks/my-work`).
2. Server queries PostgreSQL for active tasks where `assigned_to_id = current_user.id`.
3. User reviews upcoming deadlines, priority flags, and task descriptions.

---

### Journey 3: Task Assignment & Execution with Blocker Handling
```
[Coordinator Creates Task in Vertical]
       ↓
[Assigns to Volunteer Member]
       ↓
[Volunteer Updates Progress: NOT_STARTED → IN_PROGRESS (40%)]
       ↓
[Volunteer Hits Blocker: Transitions to BLOCKED + Remarks]
       ↓
[Health Updates to BLOCKED; Supervisor Alerted]
       ↓
[Coordinator Resolves Blocker → Resumes IN_PROGRESS (85%)]
       ↓
[Volunteer Completes Work → Transitions to COMPLETED (100%)]
```
1. Coordinator creates task `Pitch Setup & Goal Padding` assigned to Volunteer.
2. Volunteer starts work, setting progress to 40% and status `IN_PROGRESS`.
3. Volunteer encounters missing equipment key: transitions status to `BLOCKED` with reason `"Key missing from security office"`. Server updates `health=BLOCKED`.
4. Coordinator receives notification, retrieves key, and updates task remarks.
5. Volunteer resumes work (`IN_PROGRESS`), completes setup, and transitions status to `COMPLETED` (100%).

---

### Journey 4: Daily Work Reporting & Supervisor Review
```
[Volunteer Completes Workday]
       ↓
[Creates Daily Report for Today's Date]
       ↓
[Submits Report: status=SUBMITTED]
       ↓
[Volunteer Self-Review Blocked (403 Forbidden)]
       ↓
[Coordinator Reviews Report, Adds Feedback]
       ↓
[Report Transitions to REVIEWED; Content Locked]
```
1. Volunteer opens Daily Report submission form.
2. Selects vertical, enters hours worked, tasks accomplished, and submit flag.
3. Attempting to submit a second report for the same date is blocked by unique constraint.
4. Submitter attempting to approve their own report is blocked with `403 Forbidden`.
5. Coordinator reviews report, enters approval feedback, and marks `REVIEWED`. Record is locked from further edits.

---

### Journey 5: Cross-Vertical Requirement Routing
```
[Football Coordinator Needs Equipment from Logistics]
       ↓
[Creates Requirement: source=Football, target=Logistics]
       ↓
[Logistics Coordinator Assigns to Logistics Officer]
       ↓
[Both Sides Exchange Threaded Messages]
       ↓
[Logistics Officer Delivers Equipment & Marks COMPLETED]
```
1. Football Coordinator creates requirement specifying requested materials and due date.
2. Logistics Coordinator receives notification in target vertical queue.
3. Logistics Coordinator assigns task to Logistics Officer.
4. Both parties exchange status updates in the requirement message thread.
5. Logistics Officer marks requirement `COMPLETED`.

---

### Journey 6: Event Readiness & Execution
```
[Sports Core Creates Tournament Event]
       ↓
[System Auto-Seeds 8 Readiness Checkpoints]
       ↓
[Event Team Updates Checkpoints: PENDING → COMPLETED]
       ↓
[All Checkpoints Verified → Event Transitions to READY]
       ↓
[Tournament Starts → IN_PROGRESS → COMPLETED → ARCHIVED]
```
1. Sports Core creates `Annual Inter-College Sports Cup`.
2. System auto-initializes the 8 canonical checkpoints (`VENUE_BOOKING`, `EQUIPMENT_CHECK`, `MEDICAL_STANDBY`, `SECURITY_CLEARANCE`, `OFFICIALS_ASSIGNMENT`, `SCHEDULE_PUBLISHED`, `HOSPITALITY_READY`, `CONTINGENCY_PLAN`).
3. Assigned leads update checkpoints with status, completion dates, and remarks.
4. When all checkpoints are completed, event moves to `READY`, then `IN_PROGRESS` on match day, and `COMPLETED` upon tournament conclusion.

---

### Journey 7: Directive Issuance & Mandatory Acknowledgement Roster
```
[Admin / Sports Core Issues Mandatory Directive]
       ↓
[Server Auto-Generates Acknowledgement Roster for Vertical Members]
       ↓
[Users Receive High-Priority Notification]
       ↓
[Each User Acknowledges with Notes: status=ACKNOWLEDGED]
       ↓
[Supervisor Monitors Compliance Percentage in Dashboard]
```
1. Admin issues directive `Emergency Weather Protocol 2026` scoped to `VERTICAL`.
2. Server queries all active members of the vertical and seeds individual `DirectiveAcknowledgement` rows with status `PENDING`.
3. Users receive alert and submit acknowledgement note.
4. Compliance tracker updates in real-time.

---

### Journey 8: Ownership Transfer Governance
```
[Task Owner Reassignment Needed (e.g. Leave / Handover)]
       ↓
[Current Owner Submits Ownership Transfer Request]
       ↓
[Requester Self-Approval Blocked (403 Forbidden)]
       ↓
[Vertical Supervisor Reviews & Approves Transfer]
       ↓
[Task Assigned Owner Atomically Updated in PostgreSQL]
```
1. Current task owner submits transfer request specifying new owner and justification.
2. Server validates target user belongs to the task's vertical division.
3. Requester cannot approve transfer.
4. Supervisor approves request: server updates `Task.assigned_to_id` to new owner and marks transfer `COMPLETED`.
