# FEATURE GAP MATRIX
## Paradox Sports Operations Management System (OMS)

**Audit Date:** September 1, 2026  
**Document Status:** SPECIFICATION & AUDIT ONLY (Zero Code/DB Changes)  

---

## 1. Comprehensive Operational Inventory & Gap Assessment

The matrix below evaluates all 20 internal operational areas of the Sports Department OMS against the existing implementation, identifying what is complete, what needs modification, what is missing, what should be merged/separated, and the priority for any future implementation.

| Operational Area | Existing Model / Table | Existing API Routes | Current Status | Assessment (KEEP / MODIFY / MERGE / SEPARATE / NEW / REMOVE) | Identified Gaps / Operational Nuances | Priority |
|---|---|---|---|---|---|---|
| **Master Calendar** | `calendar_entries` | `/api/v1/calendar` | Implemented (Phase 3) | **MODIFY** | Currently lacks recurrence rules (`daily`, `weekly`, `monthly`) and dynamic color coding / event sync links. | **HIGH** |
| **Master Tasks** | `tasks`, `task_comments`, `task_history` | `/api/v1/tasks` | Implemented (Phase 3) | **KEEP** | Complete. Supports blocker lifecycle, health recalculation, audit trail, single assignee per task. | **CRITICAL** |
| **My Work** | Server-side derived query on `tasks` | `/api/v1/tasks/my-work` | Implemented (Phase 3) | **MODIFY** | Filter is currently task-only. Needs consolidation to aggregate user-assigned Tasks, Meetings, Directives, and Event duties into a single dashboard view. | **HIGH** |
| **Issue & Escalation Register** | `issues`, `issue_history` | `/api/v1/issues` | Implemented (Phase 3) | **KEEP** | Complete. Supports `CONFIDENTIAL` IDOR protection, escalation target, resolution summaries. | **CRITICAL** |
| **Daily Work Report** | `daily_work_reports` | `/api/v1/reports/daily` | Implemented (Phase 3) | **KEEP** | Complete. Unique date-user constraint, self-review block, supervisor review flow. | **CRITICAL** |
| **Weekly Report** | None (Native Model Missing) | `/api/v1/reports/admin/analytics` | Partial (Via Form / Analytics) | **NEW / MERGE** | Should be implemented either as an auto-aggregated rollup of Daily Reports or a structured weekly form template rather than a separate isolated table. | **MEDIUM** |
| **Meeting & Action Log** | `meetings`, `meeting_participants` | `/api/v1/meetings` | Implemented (Phase 4) | **MODIFY** | Supports scheduling, RSVP, and rescheduling. Needs explicit "Action Item &rarr; Task conversion" shortcut link. | **MEDIUM** |
| **Communication Tracker** | `communication_logs` | `/api/v1/communications` | Implemented (Phase 5) | **KEEP** | Complete. Preserves phone calls, external notices, emails, and reference links. | **MEDIUM** |
| **Team Database** | `users`, `user_verticals`, `user_roles` | `/api/v1/admin/users`, `/api/v1/organization` | Implemented (Phase 1, 2) | **MODIFY** | Supports users, roles, verticals. Needs richer metadata (sports specialization, emergency contact info, active volunteer status) stored as structured profile metadata. | **HIGH** |
| **Recruitment Assessment** | None (Native Model Missing) | Form Submissions (`/api/v1/forms`) | Operational via Forms | **KEEP (VIA FORMS)** | Best handled via the configurable Forms Engine (`Form` -> `FormSubmission` -> Transformation) rather than a rigid static table. | **LOW** |
| **Event Dashboard** | Server-side aggregation on `events` | `/api/v1/events`, `/api/v1/analytics/events` | Implemented (Phase 4) | **KEEP** | Complete. Real-time metric summaries across status, budget, timeline, and vertical. | **HIGH** |
| **Event Readiness** | `event_readiness_items` | `/api/v1/events/{id}/readiness` | Implemented (Phase 4) | **KEEP** | Complete. 8 canonical checkpoints seeded on event creation with individual audit notes. | **CRITICAL** |
| **Internal Forms** | `forms`, `form_versions`, `form_submissions` | `/api/v1/forms`, `/api/v1/form-submissions` | Implemented (Phase 4) | **KEEP** | Complete. Dynamic JSON schemas, version locking, validation rules, atomic transformation into `TASK`/`EVENT`/`REQUIREMENT`/`ISSUE`. | **CRITICAL** |
| **Announcements** | `announcements` | `/api/v1/announcements` | Implemented (Phase 5) | **KEEP** | Complete. Scoped broadcasting (`ALL`, `VERTICAL`, `USER`), expiration timestamps. | **HIGH** |
| **Directives** | `directives`, `directive_acknowledgements` | `/api/v1/directives` | Implemented (Phase 5) | **KEEP** | Complete. Mandatory instructions with auto-generated compliance acknowledgement rosters. | **CRITICAL** |
| **Notifications** | `notifications` | `/api/v1/notifications` | Implemented (Phase 5) | **KEEP** | Complete. High-priority attention mechanism with unread/read state tracking. | **HIGH** |
| **Ownership Transfers** | `ownership_transfers` | `/api/v1/transfers` | Implemented (Phase 5) | **KEEP** | Complete. Supervised resource handover for Tasks, Events, Requirements with self-approval blocks. | **HIGH** |
| **Audit Trail** | `audit_logs` | `/api/v1/admin/audit-logs` | Implemented (Phase 2) | **KEEP** | Complete. Immutable, append-only logging of all state mutations across all entities. | **CRITICAL** |
| **Analytics & Reporting** | `admin_reporting_service.py`, `analytics_service.py` | `/api/v1/analytics`, `/api/v1/reports/admin` | Implemented (Phase 5) | **KEEP** | Complete. Task health, event readiness, vertical performance, CSV/JSON data export. | **HIGH** |
| **Administration** | `system_configs`, `roles`, `permissions` | `/api/v1/admin` | Implemented (Phase 2, 5) | **KEEP** | Complete. RBAC management, dynamic system configuration, user enabling/disabling. | **CRITICAL** |

---

## 2. Capability Evaluation Breakdown

### A. What Exists & Is Correct (KEEP)
- Core Task Engine (Single ownership, blocker state machine, vertical scoping).
- Canonical 7-Role RBAC with server-authoritative effective permissions.
- Issue Register with `CONFIDENTIAL` IDOR protection.
- Daily Work Reports with self-review block and duplicate suppression.
- Event Management with 8 auto-seeded readiness checkpoints.
- Advanced Versioned Forms with transactional entity transformation.
- Directives with individual acknowledgement compliance rosters.
- Tamper-proof append-only audit trail and rate limiting.

### B. What Needs Modification (MODIFY)
- **My Work Aggregation:** Expand beyond tasks to aggregate assigned Meetings, pending Directive Acknowledgements, and Event duties.
- **Master Calendar:** Add support for recurring schedule rules and direct entity cross-linking.
- **Meeting Actions:** Provide one-click transformation from Meeting Action Item into a Master Task.
- **Team Database Profiles:** Allow optional sports specialization metadata (e.g. Referee, Ground Staff, First Aid).

### C. What Is Missing & Should Be Handled via Forms (NEW / VIA FORMS)
- **Recruitment Assessments:** Should NOT have a rigid database table; must be managed via the dynamic Forms Engine.
- **Weekly Reporting:** Should be an auto-generated rollup view of approved Daily Reports or a structured weekly form.

### D. Unnecessary Infrastructure (REMOVE / PROHIBIT)
- Dedicated Redis caching (Sliding window in-memory rate limiting in PostgreSQL stack is sufficient).
- External document/media storage (OMS stores metadata + links; no raw binary blobs in database).
- Rigid separate tables for one-off survey/feedback forms (handled completely by generic Forms Engine).
