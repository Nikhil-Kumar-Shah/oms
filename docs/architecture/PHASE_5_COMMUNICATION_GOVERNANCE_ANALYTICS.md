# Phase 5: Communication + Governance + Analytics Architecture

## 1. Overview & Core Mission

Phase 5 establishes the **Organizational Control & Operational Intelligence Layer** for the Paradox Sports Operations Management System (OMS). It bridges the operational execution layers developed in Phases 1 through 4 (Organization, Tasks, Events, Requests, Meetings, Forms) with targeted broadcast communication, operational directives, governed resource transfers, immutable compliance auditing, typed configuration, and real-time PostgreSQL-backed operational intelligence.

---

## 2. Structural & Architectural Invariants

1. **Zero Department Invariant**: The organizational hierarchy remains strictly `Organization -> Vertical -> User` and `Event -> Event Team Profile / Event Members`. No department concepts exist.
2. **Event Team Communication & Analytics Isolation**: Event Team profiles are isolated on the server. They only receive announcements and analytics scoped to `ALL`, `EVENT_TEAM`, or their associated `event_id`. They cannot view internal vertical announcements, vertical communications, or organizational performance intelligence.
3. **Four-Eyes Governance & Self-Approval Prevention**: Governed resource transfers (`TASK`, `EVENT`, `REQUIREMENT`) require supervisor review. Requesters or current owners cannot approve their own requests (`ForbiddenException`).
4. **Append-Only Audit Immutability**: All security, administrative, and governance actions append records to the `audit_logs` table. Any attempt to update or delete an audit record raises `ImmutableAuditException`.
5. **Typed Configuration & Secret Protection**: Configuration values are strongly typed (`STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `JSON`). Secrets and credentials are barred from database storage.
6. **Live PostgreSQL Analytics**: All operational metrics, performance indicators, and administrative compliance reports are computed directly from live relational tables (no mock data, no synthetic counters).

---

## 3. Component Breakdown & Data Models

### A. Communication Layer

```
                        ┌───────────────────────────────┐
                        │         Announcement          │
                        ├───────────────────────────────┤
                        │ scope: ALL / VERTICAL / USER /│
                        │        EVENT / EVENT_TEAM     │
                        │ event_id: FK -> events.id     │
                        │ vertical_id: FK -> verticals  │
                        └───────────────┬───────────────┘
                                        │ Dispatches
                                        ▼
┌──────────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────────┐
│        Directive         │    │       Notification        │    │    CommunicationLog       │
├──────────────────────────┤    ├───────────────────────────┤    ├───────────────────────────┤
│ scope: ALL/VERTICAL/USER │    │ recipient_id: FK -> users │    │ type: EMAIL/OFFICIAL_MSG..│
│ requires_ack: bool       │    │ type: TASK/EVENT/TRANSFER │    │ vertical_id / event_id    │
│ roster: DirectiveAck[]   │    │ read_status: UNREAD/READ  │    │ ref_link / remarks        │
└──────────────────────────┘    └───────────────────────────┘    └───────────────────────────┘
```

#### 1. Announcements (`announcements`)
- **Scopes**: `ALL`, `VERTICAL`, `USER`, `EVENT`, `EVENT_TEAM`.
- **Isolation Rule**: `AnnouncementService.list_announcements` inspects the caller's role. If `EVENT_TEAM`, it automatically filters to only announcements matching `ALL`, `EVENT_TEAM`, or `(EVENT and event_id == team.event_id)`. Internal vertical communications are strictly hidden.
- **Publication & Notifications**: Publishing an announcement dispatches attention notifications to targeted active users within the scope.

#### 2. Directives (`directives` & `directive_acknowledgements`)
- **Acknowledgement Flow**: When a directive is issued with `requires_acknowledgement=True`, a roster of `DirectiveAcknowledgement` records is initialized.
- **Duplicate Prevention**: `DirectiveService.acknowledge_directive` strictly checks that the caller matches `user_id`, and that previous status is not already `ACKNOWLEDGED`. Duplicate submissions raise `ValidationException`.
- **Notification Separation**: Reading a notification does NOT acknowledge a directive. Acknowledging a directive requires explicit API invocation with optional execution notes.

#### 3. Notifications (`notifications`)
- **Ownership Isolation**: `mark_as_read`, `mark_all_as_read`, and `dismiss_notification` strictly verify `notif.recipient_id == current_user.id`. Cross-user access raises `ForbiddenException`.

#### 4. Communication Tracker (`communication_logs`)
- **Purpose**: Formal operational record of external correspondence (emails, calls, notices, venue security agreements).
- **Linkage**: Explicit foreign keys to `vertical_id` and `event_id` with filtering capabilities.

---

### B. Governance & Control Layer

#### 1. Governed Ownership Transfers (`ownership_transfers`)
- **Supported Resources**: `TASK`, `EVENT`, `REQUIREMENT`.
- **Workflow**:
  1. Requester submits transfer request (`TransferStatus.PENDING`).
  2. Four-eyes validation checks that target user is `ACTIVE` and assigned to the resource's vertical division.
  3. Reviewer approves/rejects. Self-approval is rejected (`ForbiddenException`).
  4. On approval, the underlying entity is mutated atomically:
     - Task: `task.assigned_to_id = requested_owner_id`
     - Event: `event.primary_poc_id = requested_owner_id`
     - Requirement: `req.assignee_id = requested_owner_id`
  5. Attention notifications are dispatched to both the original and new owners.

#### 2. Immutable Audit Center (`audit_logs`)
- **Fields**: `timestamp`, `action`, `resource_type`, `resource_id`, `outcome`, `actor_id`, `correlation_id`, `ip_address`, `details`.
- **Immutability Enforcement**: `AuditService.update_record()` and `AuditService.delete_record()` raise `ImmutableAuditException`.

#### 3. System Configuration (`system_configs`)
- **Value Types**: `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `JSON`.
- **Server Validation**: Values are parsed and validated against their defined `ConfigValueType`. Invalid conversions raise `ValidationException`.

---

### C. Operational Intelligence & Analytics Layer

#### 1. Operational Dashboard (`GET /api/v1/analytics/dashboard`)
Real-time summary aggregating:
- `active_tasks`, `completed_tasks`, `overdue_tasks`, `blocked_tasks`
- `open_issues`, `escalated_issues`
- `upcoming_meetings`
- `pending_requirements`
- `event_readiness_avg_pct`
- `reporting_compliance_pct`
- `pending_directives`
- `outstanding_approvals` (transfers + requested meetings + form submissions)

#### 2. Performance Indicators (`GET /api/v1/analytics/indicators`)
Exact mathematical formulations:
- **Task Completion Rate**: `completed_tasks / total_tasks * 100`
- **Overdue Task Rate**: `overdue_tasks / total_tasks * 100`
- **Issue Resolution Rate**: `resolved_issues / total_issues * 100`
- **Requirement Resolution Rate**: `completed_requirements / total_requirements * 100`
- **Meeting RSVP Rate**: `accepted_rsvps / total_invited_rsvps * 100`
- **Reporting Compliance Rate**: `actual_submitted_reports / (active_coordinators * 7) * 100`
- **Event Readiness Average**: `sum(completed_checkpoints / total_checkpoints * 100) / total_events`
- **Operational Escalation Rate**: `(escalated_reqs + escalated_issues) / (total_reqs + total_issues) * 100`

#### 3. Administrative Compliance Reports (`GET /api/v1/admin/reports/compliance`)
- Evaluates reporting consistency for every active operator across configurable historical windows (default 7 days).

---

## 4. Alembic Migration History

| Revision ID | Description |
|---|---|
| `a1b2c3d4e5f6` | Initial Core Schema (Phase 1 Organization, Users, Roles, Permissions) |
| `b2c3d4e5f6a1` | Work Management & Coordination Schema (Phase 2 Tasks, Reports, Issues, Events, Checkpoints) |
| `c3d4e5f6a1b2` | Requests, Meetings, Forms & Workflows Schema (Phase 4 Cross-Vertical Requirements, Meetings, Dynamic Form Schemas) |
| `d4e5f6a1b2c3` | Communication, Governance & Analytics Schema (Phase 5 `EVENT`/`EVENT_TEAM` Announcement Scopes, `event_id` in Announcements and Communication Logs) |

---

## 5. Verification Matrix

| Test Suite | Tests | Result |
|---|---|---|
| `tests/test_phase5_communication_governance_analytics_acceptance.py` | 9 Acceptance Tests | **PASSED (100%)** |
| `scripts/verify_phase5_communication_governance_analytics.py` | 7-Step PostgreSQL Verification | **PASSED (100%)** |
| Full OMS Regression Suite (`pytest tests/`) | 166 Tests across 29 modules | **PASSED (100%)** |
