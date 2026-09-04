# Phase 4 — Event & Event Team Frontend Separation

## 1. Executive Summary

Phase 4 establishes the clear, authoritative frontend separation between **Internal Operations** and **Event Team Operations** for the Paradox Sports Organizational Management System (OMS).

The system enforces strict operational boundaries, authoritative PostgreSQL persistence, server-side data minimization, deterministic state machine lifecycles, single designated POC governance, readiness checkpoints, and cross-event tenant isolation.

---

## 2. Architecture & Operational Boundary Separation

```
+-----------------------------------------------------------------------------------+
|                              PARADOX SPORTS OMS                                  |
+-----------------------------------------------------------------------------------+
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │    INTERNAL OPERATIONS    │                   │   EVENT TEAM OPERATIONS   │
   │ (/events, /events/[id])   │                   │       (/event-team)       │
   ├───────────────────────────┤                   ├───────────────────────────┤
   │ * Full Event Catalog      │                   │ * Self-Service Workspace  │
   │ * State Machine Control   │                   │ * Isolated to Assigned    │
   │ * POC Group Governance    │                   │   Event only              │
   │ * 8 Readiness Checkpoints │                   │ * Team Roster Management  │
   │ * Linked Cross-Operations │                   │ * Contact Coordinates     │
   │ * Org Governance & Audit  │                   │ * Zero Internal Data Leak │
   └───────────────────────────┘                   └───────────────────────────┘
```

---

## 3. Implemented Components & Frontend Routes

### 3.1 Event Catalog (`frontend/app/events/page.tsx`)
- **Live Filtering**: Search query, Vertical filter, Status pill selectors (`ALL`, `PLANNING`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `ARCHIVED`).
- **Operational Metrics**: Active Events, In Planning, Completed, Average Readiness %.
- **Event Grid & List**: Color-coded status badges, vertical tag, date/time, venue, Event Head, Head POC, and visual readiness progress indicator.
- **Event Creation Modal**: Real-time validation, vertical assignment, planned date/time, venue, society name, and primary POC selection.

### 3.2 Event Detail & Governance Dashboard (`frontend/app/events/[id]/page.tsx`)
- **Authoritative Lifecycle State Machine**:
  - `PLANNING` $\rightarrow$ `IN_PROGRESS` | `CANCELLED`
  - `IN_PROGRESS` $\rightarrow$ `COMPLETED` | `CANCELLED`
  - `COMPLETED` $\rightarrow$ `ARCHIVED`
  - `CANCELLED` $\rightarrow$ `ARCHIVED`
  - `ARCHIVED` $\rightarrow$ Terminal
- **Readiness Checkpoints**:
  - 8 core categories: Concept & Approvals, Venue & Facilities, Equipment & Supplies, Staffing & Volunteers, Marketing & Registration, Safety & Medical, Technical & Timing, Post-Event Wrap-up.
  - Interactive status sign-off (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `NOT_APPLICABLE`), evidence link attachments, and remarks.
- **POC Group Governance Card (`frontend/components/events/POCGroupCard.tsx`)**:
  - Designated **Head POC** (exactly 1 active user).
  - Designated **POC Members** (vertical-scoped user list).
  - Quick assignment modal with authoritative backend persistence.
- **Team Roster & Members**:
  - Role management (`HEAD`, `COORDINATOR`, `MEMBER`, `VOLUNTEER`, `EXTERNAL_POC`, `LIAISON`).
- **Linked Cross-Vertical Operations**:
  - Scoped Tasks, Requirements, Meetings, Issues associated with the event.

### 3.3 Event Team Self-Service Profile (`frontend/app/event-team/page.tsx`)
- **Self-Service Workspace**:
  - Accessible via `/event-team` by authenticated event team representatives.
  - Displays linked event name, status, and dates without exposing internal organization data.
  - Team profile card with head contact details (email, phone, notes).
  - Player/member roster table with roles and jersey/contact details.
- **Profile Edit Modal**:
  - Real-time editing of team name, contact details, head phone, notes, and dynamic roster member additions/removals.
  - Server-side commit via `PUT /api/v1/event-teams/me`.

---

## 4. Security & Data Minimization Verification

### 4.1 Cross-Event & Tenant Isolation
| Scenario | Request | Expected Result | Verified Result |
| :--- | :--- | :--- | :--- |
| **Team A accesses own Event A** | `GET /api/v1/events/{event_a_id}` | `200 OK` | `200 OK` (PASS) |
| **Team A accesses Event B** | `GET /api/v1/events/{event_b_id}` | `403 Forbidden` | `403 Forbidden` (PASS) |
| **Team B accesses own Event B** | `GET /api/v1/events/{event_b_id}` | `200 OK` | `200 OK` (PASS) |
| **Team B accesses Event A** | `GET /api/v1/events/{event_a_id}` | `403 Forbidden` | `403 Forbidden` (PASS) |
| **Team A accesses Team B profile ID** | `GET /api/v1/event-teams/{team_b_id}` | `403 Forbidden` | `403 Forbidden` (PASS) |
| **Event Team accesses Admin Audit Logs** | `GET /api/v1/admin/audit-logs` | `403 Forbidden` | `403 Forbidden` (PASS) |

### 4.2 Lifecycle State Transitions
| Current Status | Target Status | Validation Rule | Verified Result |
| :--- | :--- | :--- | :--- |
| `PLANNING` | `ARCHIVED` | Invalid transition | `422 Unprocessable Entity` (PASS) |
| `PLANNING` | `IN_PROGRESS` | Valid transition | `200 OK` (PASS) |
| `IN_PROGRESS` | `COMPLETED` | Valid transition | `200 OK` (PASS) |
| `COMPLETED` | `ARCHIVED` | Valid transition | `200 OK` (PASS) |

---

## 5. Verification Suite Results

1. **TypeScript (`npm run typecheck`)**: Passed with 0 errors.
2. **ESLint (`npm run lint`)**: Passed with 0 errors and 0 warnings.
3. **Next.js Production Build (`npm run build`)**: 27 routes compiled successfully.
4. **End-to-End Database Verification (`scripts/verify_phase4_event_frontend.py`)**: 100% Passed.
5. **Backend Pytest Regression Suite (`python -m pytest tests/ -q`)**: 189 / 189 tests passed (100%).
