# Phase 3: Core Operational System Architecture

## 1. System Overview
Phase 3 establishes the internal work-management foundation for **Paradox Sports OMS**, encompassing:
1. **Master Tasks** (`tasks`, `task_history`, `task_comments`)
2. **My Work** (Server-authoritative authenticated personal work view)
3. **Master Calendar** (`calendar_entries` with category, priority, status, and audience scope filtering)
4. **Issue & Escalation Register** (`issues`, `issue_history` with sensitivity tiers and escalation tracking)
5. **Daily Work Reports** (`daily_work_reports` with strict unique date constraints and supervisor self-review prevention)
6. **Weekly Reporting** (`weekly_reports` with summary aggregation)

The architecture strictly follows:
```
Browser / Client
       ↓
    FastAPI
       ↓
 Authentication
       ↓
Authorization / RBAC
       ↓
   Validation
       ↓
 Service Layer
       ↓
 SQLAlchemy 2.x
       ↓
   PostgreSQL
```

---

## 2. Master Tasks System
- **Models**: `Task`, `TaskHistory`, `TaskComment`
- **Task Types**: `ROUTINE`, `EVENT`, `MILESTONE`, `DOCUMENTATION`, `MEETING_FOLLOW_UP`.
- **Priority**: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- **Status Lifecycle**: `NOT_STARTED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `BLOCKED` $\rightarrow$ `COMPLETED` / `CANCELLED`.
- **Health Calculation**:
  - `COMPLETE`: Status is `COMPLETED` (100% progress).
  - `BLOCKED`: Status is `BLOCKED`.
  - `OVERDUE`: Current time exceeds `deadline` and status is not `COMPLETED`.
  - `AT_RISK`: Within 24 hours of deadline and completion percentage < 50%.
  - `ON_TRACK`: Progress progressing normally.
- **Assignment Authorization**: Target user must have `ACTIVE` status and be assigned to the task's vertical division.
- **History & Immutability**: All changes (creation, assignment, status transition, completion) are atomically written to `task_history` and `audit_logs`.

---

## 3. My Work
- **Endpoint**: `GET /api/v1/my-work`
- **Identity Rule**: The server resolves identity strictly from the authenticated session token. Any query parameter attempting to spoof `user_id` is ignored.
- **Filtering**: Supports `status_filter` (`active`, `overdue`, `blocked`, `completed`, `upcoming`) and `priority`.

---

## 4. Master Calendar
- **Model**: `CalendarEntry`
- **Activity Categories**: `ACTIVITY`, `MILESTONE`, `REVIEW_MEETING`, `INTERVIEW`, `REPORT_DEADLINE`, `ONBOARDING`, `ORIENTATION`, `EVENT`, `MEETING`.
- **Priority**: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- **Status**: `PLANNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`.
- **Deadline Types**: `HARD_DEADLINE`, `SOFT_DEADLINE`, `INFORMATIONAL`.
- **Audience Scope Enforcement**:
  - `ALL` / `ORGANIZATION`: Visible to all active organization members.
  - `VERTICAL`: Visible only to members assigned to that vertical division, or executive leadership (`ADMIN` / `SPORTS_CORE` / `DEPUTY_CORE`).

---

## 5. Issue & Escalation Register
- **Models**: `Issue`, `IssueHistory`
- **Status**: `OPEN`, `IN_PROGRESS`, `BLOCKED`, `ESCALATED`, `RESOLVED`, `CLOSED`, `CANCELLED`.
- **Sensitivity Classification**: `NORMAL`, `SENSITIVE`, `CONFIDENTIAL`.
- **Authorization & IDOR Protection**:
  - `CONFIDENTIAL` issues can only be accessed by the creator, the designated assignee, or users with `issues.confidential.read` permission / `ADMIN` role. Probing by unauthorized users returns `403 Forbidden`.
- **Escalation**: Records target, action required, and deadline in `issue_history`.

---

## 6. Daily Work Reports
- **Model**: `DailyWorkReport`
- **Status**: `DRAFT`, `SUBMITTED`, `REVIEWED`, `RETURNED`, `FLAGGED`.
- **Integrity**: Unique constraint on `(user_id, report_date)` prevents duplicate reports.
- **Self-Review Prohibition**: An author is strictly prevented from reviewing or approving their own report (`ForbiddenException: Self-review violation`).

---

## 7. Weekly Reports
- **Model**: `WeeklyReport`
- **Status**: `DRAFT`, `SUBMITTED`, `REVIEWED`.
- **Integrity**: Unique constraint on `(user_id, week_start_date)`.
- **Review**: Supervisor review with feedback comments.

---

## 8. Zero Hard-Deletion Policy
All operational resources are preserved in PostgreSQL with lifecycle state transitions (`CANCELLED`, `CLOSED`, `ARCHIVED`, `RETURNED`). HTTP `DELETE` methods are disabled (`405 Method Not Allowed`).

---

## 9. API Summary

### Master Tasks (`/api/v1/tasks` & `/api/v1/my-work`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/my-work` | Authenticated user personal work | Authenticated |
| `GET` | `/api/v1/tasks` | List master tasks with filters | `tasks.read` |
| `POST` | `/api/v1/tasks` | Create master task | `tasks.create` |
| `GET` | `/api/v1/tasks/{id}` | Task detail | `tasks.read` |
| `PATCH` | `/api/v1/tasks/{id}` | Update task details | `tasks.update` |
| `POST` | `/api/v1/tasks/{id}/transition` | Transition task status | `tasks.transition` |
| `POST` | `/api/v1/tasks/{id}/assign` | Assign task to user in vertical | `tasks.assign` |
| `GET` | `/api/v1/tasks/{id}/comments` | List task comments | `tasks.read` |
| `POST` | `/api/v1/tasks/{id}/comments` | Add task comment | Authenticated |
| `GET` | `/api/v1/tasks/{id}/history` | List task history | `tasks.read` |

### Master Calendar (`/api/v1/calendar`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/calendar` | List calendar entries with audience filtering | Authenticated |
| `POST` | `/api/v1/calendar` | Create calendar entry | `calendar.create` |
| `GET` | `/api/v1/calendar/{id}` | Get calendar entry | Authenticated |
| `PATCH` | `/api/v1/calendar/{id}` | Update calendar entry | `calendar.update` |

### Issues & Escalations (`/api/v1/issues`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/issues` | List issues with sensitivity filtering | Authenticated |
| `POST` | `/api/v1/issues` | Raise issue ticket | `issues.create` |
| `GET` | `/api/v1/issues/{id}` | Issue detail (sensitivity checked) | Authenticated |
| `PATCH` | `/api/v1/issues/{id}` | Update issue | `issues.update` |
| `POST` | `/api/v1/issues/{id}/transition` | Transition issue status | `issues.update` |
| `POST` | `/api/v1/issues/{id}/escalate` | Escalate issue | `issues.escalate` |
| `GET` | `/api/v1/issues/{id}/history` | List issue history | `issues.read` |

### Work Reports (`/api/v1/reports`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/reports/daily` | List daily work reports | Authenticated |
| `POST` | `/api/v1/reports/daily` | Submit daily work report | Authenticated |
| `GET` | `/api/v1/reports/daily/{id}` | Daily report detail | Authenticated |
| `POST` | `/api/v1/reports/daily/{id}/review` | Supervisor review daily report | `reports.review` |
| `GET` | `/api/v1/reports/weekly` | List weekly reports | Authenticated |
| `POST` | `/api/v1/reports/weekly` | Submit weekly report | Authenticated |
| `GET` | `/api/v1/reports/weekly/{id}` | Weekly report detail | Authenticated |
| `POST` | `/api/v1/reports/weekly/{id}/review` | Review weekly report | `reports.weekly.review` |
