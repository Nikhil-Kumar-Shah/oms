# Phase 3 — Internal Work Management UI Documentation

## Paradox Sports Operations Management System (OMS)

### Overview
Phase 3 elevates the Paradox Sports Operations Management System from a foundational shell into a production-grade operational work-management system. It establishes authoritative user interfaces for tasks, personal workflows, organizational calendars, operational issues, and supervisory reporting, fully integrated with PostgreSQL and protected by fine-grained RBAC.

---

### Core Principles & Architecture

1. **Backend as the Single Authoritative Source of Truth**:
   - Zero mock data or local state illusions.
   - All mutations execute through typed API calls to FastAPI, commit to PostgreSQL transactions, and trigger fresh GET queries to update the UI.
2. **My Work as a Projection**:
   - `GET /api/v1/workspace/my-work` serves as an authoritative personal operational projection across Master Tasks, Directives, and Meetings.
   - No duplicate tables or divergent models.
3. **Role & Permission Aware Interfaces**:
   - Buttons, modals, and actions dynamically adapt based on the user's permissions (`tasks.create`, `tasks.assign`, `tasks.transition`, `issues.escalate`, `reports.review`, etc.).
   - Event Team users are strictly isolated from internal operational data through both route-level AppShell protection and backend 403 enforcement.
4. **Data-Driven Selectors**:
   - All verticals, users, priorities, and statuses are loaded dynamically from `/api/v1/organization/verticals` and `/api/v1/admin/users`.

---

### Key Workspaces & Routes

| Route | Workspace | Core Capabilities |
| :--- | :--- | :--- |
| `/tasks` | Master Tasks Register | Search, filter by status/priority/vertical, task creation modal with real-time validation, table view with progress bars and health indicators. |
| `/tasks/[id]` | Task Details & Lifecycle | Task status transitions (`NOT_STARTED` → `IN_PROGRESS` → `COMPLETED`), operational blockers, unblocking, reassignment, vertical escalation, remarks, evidence links, comment threads, and immutable audit history. |
| `/my-work` | Personal Projection | Live KPI statistics, filtered tabs (Active Tasks, Overdue, Blocked, Directives, Meetings), 1-click status transitions, and synchronous workspace synchronization. |
| `/calendar` | Master Calendar | Dual-view (Interactive Month Grid & Chronological List), category filtering (`ACTIVITY`, `MEETING`, `REPORT_DEADLINE`, `EVENT`, etc.), schedule item modal, and navigable links to linked Master Tasks. |
| `/issues` | Issue Register | Issue logging with sensitivity indicators (`NORMAL`, `SENSITIVE`, `CONFIDENTIAL`), status filters, and vertical scoping. |
| `/issues/[id]` | Issue Escalation & Resolution | Detailed deficiency logging, formal routing to leadership (`escalation_target` + `escalation_action`), resolution notes, and audit history. |
| `/reports` | Work Reports & Rollups | Daily activity submission, supervisor review queue with four-eyes self-review prevention, and dynamic weekly rollups. |

---

### UI Components & Primitives

- `StatusBadge` (`frontend/components/common/StatusBadge.tsx`): Canonical color-coded badges for all operational states (`NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `REVIEWED`, etc.).
- `PriorityBadge` (`frontend/components/common/PriorityBadge.tsx`): Visual priority indicators (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- `HealthIndicator` (`frontend/components/common/HealthIndicator.tsx`): Authoritative health pills (`ON_TRACK`, `AT_RISK`, `OVERDUE`, `BLOCKED`, `COMPLETE`).
- `EmptyState` (`frontend/components/common/EmptyState.tsx`): Standardized empty state presentation with contextual call-to-action buttons.
- `ConfirmDialog` (`frontend/components/common/ConfirmDialog.tsx`): Accessible modal dialogs for critical state mutations (blockers, escalations, reviews).

---

### Verification & Testing Summary

1. **TypeScript & Static Analysis**:
   - `npm run typecheck`: Passed with 0 errors.
   - `npm run lint`: Passed with 0 errors and 0 warnings.
2. **Next.js Production Build**:
   - `npm run build`: Compiled 26 prerendered static routes and dynamic routes (`/tasks/[id]`, `/issues/[id]`) cleanly on Next.js 16.3.4 (Turbopack).
3. **End-to-End Persistence & Security Suite**:
   - Executed `scripts/verify_phase3_work_management_ui.py` validating 100% of workflows against PostgreSQL:
     - Task creation, fresh GET, status transition, comments, blockers, unblocking, and completion.
     - Authoritative My Work projection.
     - Calendar creation, fresh GET, and Master Task linking.
     - Issue creation, formal escalation, and resolution.
     - Daily report submission, four-eyes self-review rejection, and supervisor review.
     - Event Team isolation and 403 Forbidden enforcement on internal operational routes.
