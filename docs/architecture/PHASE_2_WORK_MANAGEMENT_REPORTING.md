# Architecture & Operations Reference: Phase 2 — Work Management + Reporting
**Paradox Sports Operations Management System (OMS)**
*Authoritative Architectural Specification & Verification Document*

---

## 1. Executive Summary & Design Principles

Phase 2 builds the core operational work execution and reporting engine for Paradox Sports OMS. The architecture enforces PostgreSQL as the sole system of record and adheres to the following foundational constraints:
- **Zero Department Concept**: The organizational topology remains strictly `Organization -> Vertical -> User`.
- **Server-Authoritative State & Health**: All task lifecycle states, completion synchronizations, health calculations, and supervisory reviews are calculated on the backend.
- **Strict Anti-Impersonation**: Operational workspace views (`/my-work`) derive user identity strictly from the authenticated PostgreSQL session token.
- **Four-Eyes Supervisory Review Rule**: Authors are forbidden from self-reviewing their daily or weekly reports.
- **Append-Only Auditing**: Reassignments, escalations, blockers, transitions, and supervisory reviews are recorded in append-only tables (`task_history`, `audit_logs`).

---

## 2. Component Architecture

### 2.1 Master Task Lifecycle & Escalation Engine
- **Lifecycle States**: `NOT_STARTED` (`OPEN`), `IN_PROGRESS`, `PAUSED`, `BLOCKED`, `COMPLETED`, `CANCELLED`, `ARCHIVED`.
- **Completion Percentage Synchronization**:
  - `NOT_STARTED`: Enforces 0% progress.
  - `COMPLETED`: Automatically synchronizes `completion_percentage = 100` and stamps `completed_on = now()`.
- **Authoritative Health Derivation**:
  - `COMPLETE`: Status is `COMPLETED`.
  - `BLOCKED`: Status is `BLOCKED`.
  - `OVERDUE`: `now() > deadline` and not completed.
  - `AT_RISK`: Within 24 hours of deadline and progress is under 50%.
  - `ON_TRACK`: Routine progression without deadline violation.
- **Escalation Engine**:
  - Dedicated columns on `tasks`: `is_escalated`, `escalated_to_id`, `escalated_by_id`, `escalation_reason`, `escalated_at`, `escalation_status`, `escalation_resolution`, `escalation_resolved_at`.
  - Transitions: `POST /api/v1/tasks/{id}/escalate` &rarr; `POST /api/v1/tasks/{id}/resolve-escalation`.
- **Reassignment & Scoping**:
  - Reassignment (`POST /api/v1/tasks/{id}/reassign`) verifies target assignee is active and assigned to the task's vertical division.

### 2.2 My Work (Personal Operational Workspace)
- **Identity Derivation**: Uses server-side `get_current_user` dependency from the bearer session token.
- **Security**: Any client-supplied `user_id` query parameter is ignored for authorization.
- **Aggregation**: Combines active tasks, blockers, pending directives, upcoming meetings, and event duties into a single operational response.

### 2.3 Master Calendar
- **Audience Scoping**:
  - `ORGANIZATION`: Visible across the entire organization.
  - `VERTICAL`: Visible only to active users assigned to that vertical.
  - `SPECIFIC_USERS`: Filtered to designated user IDs.
- **Entity Linkages**: Direct foreign key associations to `task_id`, `event_id`, `meeting_id`, `requirement_id`.

### 2.4 Issue & Escalation Register
- **Sensitivity Levels**: `NORMAL`, `SENSITIVE`, `CONFIDENTIAL`.
- **Access Control**: Confidential issues require `issues.confidential.read` permission or `ADMIN`/`SPORTS_CORE` role, or the user must be the reporter or assignee.

### 2.5 Daily & Weekly Work Reporting
- **Duplicate Prevention**: Unique constraint and service-level validation prevent multiple submissions by the same user on the same date.
- **Four-Eyes Rule**: Prevents report authors from approving/reviewing their own reports (`HTTP 403 Forbidden`).
- **Dynamic Weekly Rollup**: `GET /api/v1/reports/weekly/rollup` queries PostgreSQL dynamically to calculate task completions, blockers, and submitted daily summaries without data duplication.

---

## 3. Database Schema & Migration

### Migration: `b2c3d4e5f6a1_phase2_task_escalation_work_management.py`
```sql
ALTER TABLE tasks ADD COLUMN is_escalated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN escalated_to_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE tasks ADD COLUMN escalated_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE tasks ADD COLUMN escalation_reason TEXT;
ALTER TABLE tasks ADD COLUMN escalated_at TIMESTAMPTZ;
ALTER TABLE tasks ADD COLUMN escalation_status VARCHAR(50);
ALTER TABLE tasks ADD COLUMN escalation_resolution TEXT;
ALTER TABLE tasks ADD COLUMN escalation_resolved_at TIMESTAMPTZ;

CREATE INDEX ix_tasks_is_escalated ON tasks (is_escalated);
CREATE INDEX ix_tasks_escalated_to_id ON tasks (escalated_to_id);
```

---

## 4. Verification Evidence

- **Automated Regression Suite**: 138/138 tests passing (100%).
- **Phase 2 Test Suite**: 9/9 specialized operational tests passing (`tests/test_phase2_work_management_reporting.py`).
- **PostgreSQL Persistence Script**: Fresh-session validation passing (`scripts/verify_phase2_work_management.py`).
