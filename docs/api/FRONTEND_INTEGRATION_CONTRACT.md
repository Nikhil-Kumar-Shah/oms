# Paradox Sports OMS: Next.js Frontend Integration Contract

**Document Version:** 1.0.0 (Phase 7 API Readiness)  
**Target Client:** Next.js (App Router / TypeScript / TailwindCSS / TanStack Query)  
**Backend Framework:** FastAPI / PostgreSQL (Server-Authoritative)  
**Base URL:** `/api/v1`  
**OpenAPI Specification:** `GET /openapi.json`  
**Interactive Documentation:** `GET /docs` (Swagger UI), `GET /redoc` (ReDoc)  
**Discovery Endpoint:** `GET /api/v1`  

---

## 1. Access Classification & Security Boundaries

```
PUBLIC
│
├── GET  /               (Minimal service liveness & metadata: { name, version, status })
├── GET  /health         (Minimal safe health status: { status: "healthy" })
├── POST /api/v1/auth/login (Unauthenticated credential exchange)
└── GET  /api/v1/health  (API router health probe)

AUTHENTICATED (JWT Bearer Token Required)
│
├── GET  /api/v1         (API discovery and resource group registry)
└── ALL  /api/v1/*       (Tasks, Workspaces, Calendar, Issues, Reports, Events, Forms, etc.)

HIGHLY RESTRICTED (HTTP Basic Authentication: API_DOCS_USERNAME / API_DOCS_PASSWORD)
│
├── GET  /docs           (Swagger UI)
├── GET  /redoc          (ReDoc Interface)
└── GET  /openapi.json   (Full OpenAPI 3.1 Schema)

DISABLED (404 Not Found)
│
└── ALL  /dev/*          (Jinja development interface removed completely)
```

### Architectural Principles for Frontend Integration

1. **Server-Authoritative Business Logic**:
   - The frontend **must never** attempt to re-implement business validation (e.g. self-review rules, vertical scoping, transition guards, readiness % calculations, or role permission tables).
   - Display state and execute actions based on server responses. Handle standard `400`, `401`, `403`, `404`, `422`, and `500` error contracts gracefully.

2. **Strict Zero Department Invariant**:
   - The hierarchy is strictly `Organization -> Vertical -> User`.
   - Never render or expect "department" dropdowns, models, or query parameters.

3. **Event Team Boundary Isolation**:
   - External event team users (`Role: EVENT_TEAM`) only have visibility into assigned events, event team profile details, and public/event-scoped announcements.
   - Internal vertical tabs, Master Tasks, My Work, Audit Logs, and Analytics endpoints are denied (`403 Forbidden`).

4. **Dynamic Projections**:
   - `My Work` (`/api/v1/workspace/my-work`) and `Master Calendar` (`/api/v1/calendar`) are dynamic server projections. Do not maintain separate local client stores for these views.

---

## 2. Authentication & Session Lifecycle

```
       [Next.js Client]                                      [FastAPI Backend]
              │                                                     │
              │──── POST /api/v1/auth/login (username, password) ──>│
              │<─── 200 OK (access_token, token_type, user info) ───│
              │                                                     │
              │──── GET /api/v1/auth/me (Bearer Token) ────────────>│
              │<─── 200 OK (id, username, roles, verticals) ────────│
              │                                                     │
              │──── POST /api/v1/auth/refresh ─────────────────────>│
              │<─── 200 OK (new access_token) ──────────────────────│
              │                                                     │
              │──── POST /api/v1/auth/logout ──────────────────────>│
              │<─── 200 OK (session revoked) ───────────────────────│
```

### Endpoints

#### `POST /api/v1/auth/login`
- **Request**:
  ```json
  {
    "username": "coordinator_field",
    "password": "Password@123"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "session": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_at": "2026-09-02T12:00:00Z"
    },
    "user": {
      "id": "7b0fa527-df2a-4318-97ec-0373809e5ee9",
      "username": "coordinator_field",
      "full_name": "Field Coordinator",
      "email": "field@paradoxsports.org",
      "account_status": "ACTIVE",
      "roles": ["COORDINATOR"],
      "verticals": [
        {
          "id": "e4a7a8d1-dcf2-4cb6-86c4-727c088ef56b",
          "name": "Field Operations",
          "is_primary": true
        }
      ]
    }
  }
  ```

#### `GET /api/v1/auth/me`
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**: Returns authenticated user profile, roles, and vertical memberships.

#### `POST /api/v1/auth/change-password`
- **Headers**: `Authorization: Bearer <token>`
- **Request**:
  ```json
  {
    "current_password": "OldPassword@123",
    "new_password": "NewSecurePassword@123"
  }
  ```

---

## 3. Standardized Error Contract

All error responses from the API conform to the following JSON structure:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Required field 'Task Name' is missing or empty",
    "details": {
      "field": "title",
      "validation_errors": []
    }
  }
}
```

### Standard HTTP Status Codes

| HTTP Status | Error Code | Description / Client Handling |
|---|---|---|
| **400 Bad Request** | `IMMUTABLE_AUDIT_LOG` / `BAD_REQUEST` | Invalid request payload or illegal immutable mutation. |
| **401 Unauthorized** | `AUTHENTICATION_FAILED` / `SESSION_EXPIRED` | Missing or invalid token. Redirect to `/login`. |
| **403 Forbidden** | `FORBIDDEN` / `ACCOUNT_INACTIVE` | Insufficient role/permission or self-review violation. Show warning banner. |
| **404 Not Found** | `ENTITY_NOT_FOUND` | Resource UUID does not exist. Show 404 view. |
| **422 Unprocessable**| `VALIDATION_ERROR` / `REQUEST_VALIDATION_ERROR` | Schema validation error. Map `details.validation_errors` to form field errors. |
| **500 Internal Error**| `INTERNAL_SERVER_ERROR` | Unexpected server error. Displays generic message (secrets stripped). |
| **503 Unavailable** | `DATABASE_UNAVAILABLE` | Database health failure. Show maintenance screen. |

---

## 4. Complete Resource Endpoints Matrix

### Master Tasks (`/api/v1/tasks`)
- `GET /api/v1/tasks` (Query: `vertical_id`, `assigned_to_id`, `status`, `priority`, `limit`, `offset`)
- `POST /api/v1/tasks` (Create Master Task)
- `GET /api/v1/tasks/{id}` (Get Task with history & comments)
- `PATCH /api/v1/tasks/{id}` (Update metadata)
- `POST /api/v1/tasks/{id}/transition` (Transition status: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED`)
- `POST /api/v1/tasks/{id}/comments` (Add operational comment)

### Operational Workspace & My Work (`/api/v1/workspace`)
- `GET /api/v1/workspace/my-work` (Personal duties: assigned tasks, meetings, open issues, pending reports, directives)

### Master Calendar (`/api/v1/calendar`)
- `GET /api/v1/calendar` (Query: `start_date`, `end_date`, `vertical_id`, `event_id`)

### Issues & Escalations (`/api/v1/issues`)
- `GET /api/v1/issues` (Query: `vertical_id`, `status`, `sensitivity`)
- `POST /api/v1/issues` (Log issue)
- `POST /api/v1/issues/{id}/escalate` (Escalate to Core)
- `POST /api/v1/issues/{id}/transition` (Transition issue state)

### Work Reports (`/api/v1/reports`)
- `GET /api/v1/reports/daily` (List daily reports)
- `POST /api/v1/reports/daily` (Submit daily work report)
- `POST /api/v1/reports/daily/{id}/review` (Supervisor four-eyes review)
- `POST /api/v1/reports/weekly` (Submit weekly summary)

### Events & Coordination (`/api/v1/events`)
- `GET /api/v1/events` (List events)
- `POST /api/v1/events` (Create event)
- `GET /api/v1/events/{id}` (Event details with readiness checklist)
- `POST /api/v1/events/{id}/poc-group` (Assign Head POC & Secondary POCs)
- `PATCH /api/v1/events/{id}/readiness/{item_id}` (Update checklist status)

### Event Teams (`/api/v1/event-teams`)
- `GET /api/v1/event-teams/{id}` (Get profile)
- `PATCH /api/v1/event-teams/{id}` (Update contacts and notes)

### Cross-Vertical Requirements (`/api/v1/requirements`)
- `GET /api/v1/requirements` (List requirements)
- `POST /api/v1/requirements` (Create requirement)
- `POST /api/v1/requirements/{id}/assign` (Assign coordinator)
- `POST /api/v1/requirements/{id}/escalate` (Escalate requirement)
- `POST /api/v1/requirements/{id}/resolve-escalation` (Resolve escalation)

### Meetings & RSVPs (`/api/v1/meetings`)
- `GET /api/v1/meetings` (List meetings)
- `POST /api/v1/meetings` (Schedule meeting)
- `POST /api/v1/meetings/{id}/rsvp` (Update RSVP: `ACCEPTED`, `DECLINED`, `TENTATIVE`)
- `POST /api/v1/meetings/{id}/action-items` (Create action item)
- `POST /api/v1/meetings/{id}/action-items/{item_id}/convert-to-task` (Convert to Master Task)

### Dynamic Forms (`/api/v1/forms`)
- `GET /api/v1/forms` (List forms)
- `POST /api/v1/forms` (Create form schema)
- `POST /api/v1/forms/{id}/publish` (Publish immutable version)
- `POST /api/v1/forms/{id}/submissions` (Submit response)
- `POST /api/v1/forms/submissions/{sub_id}/review` (Review & trigger atomic transformation)

### Announcements (`/api/v1/announcements`)
- `GET /api/v1/announcements` (List scoped announcements)
- `POST /api/v1/announcements` (Create announcement)
- `POST /api/v1/announcements/{id}/publish` (Publish & dispatch notifications)

### Directives & Acknowledgements (`/api/v1/directives`)
- `GET /api/v1/directives` (List directives)
- `POST /api/v1/directives` (Issue directive)
- `POST /api/v1/directives/{id}/acknowledge` (Acknowledge directive)

### Notifications (`/api/v1/notifications`)
- `GET /api/v1/notifications` (List notifications)
- `PATCH /api/v1/notifications/{id}/read` (Mark single notification as read)
- `POST /api/v1/notifications/mark-all-read` (Mark all as read)
- `DELETE /api/v1/notifications/{id}` (Dismiss notification)

### Governed Transfers (`/api/v1/transfers`)
- `GET /api/v1/transfers` (List ownership transfer requests)
- `POST /api/v1/transfers` (Request transfer: `TASK`, `EVENT`, `REQUIREMENT`)
- `POST /api/v1/transfers/{id}/review` (Four-eyes review & atomic ownership reassignment)

### Operational Analytics (`/api/v1/analytics`)
- `GET /api/v1/analytics/dashboard` (Live operational dashboard counters)
- `GET /api/v1/analytics/indicators` (Calculated performance indicator %s)
- `GET /api/v1/analytics/operational` (Deep operational analytics)
- `GET /api/v1/admin/reports/compliance` (Reporting compliance over date window)

---

## 5. Next.js Client Implementation Guidelines

### API Client (Axios / Fetch Interceptor Pattern)

```typescript
// lib/api-client.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('oms_access_token') : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('oms_access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### TypeScript Data Interfaces

```typescript
// types/oms.ts
export type TaskStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'CANCELLED';
export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type TaskHealth = 'ON_TRACK' | 'AT_RISK' | 'CRITICAL' | 'COMPLETE';

export interface Task {
  id: string;
  title: string;
  description?: string;
  status: TaskStatus;
  priority: TaskPriority;
  health: TaskHealth;
  completion_percentage: number;
  deadline?: string;
  vertical_id: string;
  assigned_to_id: string;
  created_at: string;
}

export interface OperationalDashboardMetrics {
  generated_at: string;
  active_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  blocked_tasks: number;
  open_issues: number;
  escalated_issues: number;
  upcoming_meetings: number;
  pending_requirements: number;
  event_readiness_avg_pct: number;
  reporting_compliance_pct: number;
  pending_directives: number;
  outstanding_approvals: number;
}
```
