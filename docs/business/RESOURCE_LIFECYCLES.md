# Resource Lifecycle State Machines
**Paradox Sports Operations Management System (OMS)**

This document defines the formal lifecycle states, allowed transitions, and side effects for all operational entities.

---

## 1. Master Task Lifecycle (`tasks`)

```
               ┌─────────────┐
               │ NOT_STARTED │
               └──────┬──────┘
                      │ start_work
                      ▼
               ┌─────────────┐   declare_blocker   ┌─────────┐
               │ IN_PROGRESS │ ──────────────────► │ BLOCKED │
               └──────┬──────┘ ◄────────────────── └─────────┘
                      │          resolve_blocker
                      │ complete_work
                      ▼
               ┌─────────────┐
               │  COMPLETED  │
               └──────┬──────┘
                      │ archive
                      ▼
               ┌─────────────┐
               │  ARCHIVED   │
               └─────────────┘
  (From any active state: CANCELLED transition available)
```

| Current State | Allowed Next States | Trigger Action | Required Fields / Conditions |
| :--- | :--- | :--- | :--- |
| `NOT_STARTED` | `IN_PROGRESS`, `CANCELLED` | `start_work`, `cancel` | Valid assignee |
| `IN_PROGRESS` | `BLOCKED`, `COMPLETED`, `CANCELLED` | `declare_blocker`, `complete`, `cancel` | `completion_percentage`, comments |
| `BLOCKED` | `IN_PROGRESS`, `CANCELLED` | `resolve_blocker`, `cancel` | `blocker_reason` required when entering |
| `COMPLETED` | `ARCHIVED` | `archive` | Supervisor verification |
| `CANCELLED` | `ARCHIVED` | `archive` | Cancellation reason |
| `ARCHIVED` | None (Terminal) | — | Read-only |

---

## 2. Operational Event Lifecycle (`events`)

```
   ┌──────────┐  start_event   ┌─────────────┐  complete_event  ┌───────────┐  archive  ┌──────────┐
   │ PLANNING │ ─────────────► │ IN_PROGRESS │ ───────────────► │ COMPLETED │ ────────► │ ARCHIVED │
   └────┬─────┘                └──────┬──────┘                  └───────────┘           └──────────┘
        │                             │
        └──────────► CANCELLED ◄──────┘
```

| Current State | Allowed Next States | Trigger Action | Side Effects |
| :--- | :--- | :--- | :--- |
| `PLANNING` | `IN_PROGRESS`, `CANCELLED` | `start_event`, `cancel` | Readiness checkpoints active |
| `IN_PROGRESS` | `COMPLETED`, `CANCELLED` | `complete_event`, `cancel` | Locks readiness items |
| `COMPLETED` | `ARCHIVED` | `archive` | Finalizes event dashboard metrics |
| `CANCELLED` | `ARCHIVED` | `archive` | Preserves all checklist and team records |
| `ARCHIVED` | None (Terminal) | — | Read-only queryable state |

---

## 3. Cross-Vertical Requirement Lifecycle (`requirements`)

```
   ┌──────┐  route_assign   ┌──────────┐  start_work   ┌─────────────┐  complete   ┌───────────┐
   │ OPEN │ ──────────────► │ ASSIGNED │ ────────────► │ IN_PROGRESS │ ──────────► │ COMPLETED │
   └───┬──┘                 └────┬─────┘               └──────┬──────┘             └─────┬─────┘
       │ reject/cancel           │ cancel                     │ declare_blocker          │ archive
       ▼                         ▼                            ▼                          ▼
   ┌──────────┐              ┌───────────┐             ┌─────────────┐             ┌───────────┐
   │ REJECTED │              │ CANCELLED │             │   BLOCKED   │             │ ARCHIVED  │
   └──────────┘              └───────────┘             └─────────────┘             └───────────┘
```

---

## 4. Issue Register Lifecycle (`issues`)

```
   ┌──────┐  assign_issue   ┌─────────────┐  escalate   ┌───────────┐  resolve   ┌──────────┐  close  ┌────────┐
   │ OPEN │ ──────────────► │ IN_PROGRESS │ ──────────► │ ESCALATED │ ─────────► │ RESOLVED │ ──────► │ CLOSED │
   └───┬──┘                 └──────┬──────┘             └─────┬─────┘            └──────────┘         └────────┘
       │                           │                          │
       └──────────────► CANCELLED ◄┴──────────────────────────┘
```

---

## 5. Daily Work Report Lifecycle (`daily_work_reports`)

```
   ┌───────┐  submit_report   ┌───────────┐  supervisor_review  ┌──────────┐
   │ DRAFT │ ───────────────► │ SUBMITTED │ ──────────────────► │ REVIEWED │
   └───────┘                  └─────┬─────┘                     └──────────┘
                                    │
                                    ├───► FLAGGED (Requires clarification)
                                    │
                                    └───► RETURNED (Requires revisions)
```

---

## 6. Advanced Form Lifecycle (`forms` & `form_submissions`)

### Form Schema Definition:
`DRAFT` &rarr; `PUBLISHED` &rarr; `ARCHIVED`

### Form Submission:
`SUBMITTED` &rarr; `UNDER_REVIEW` &rarr; `APPROVED` (Triggers native OMS entity transformation) / `REJECTED` / `RETURNED`.

---

## 7. Directive Lifecycle (`directives`)

`DRAFT` &rarr; `ISSUED` (Generates participant acknowledgement roster) &rarr; `CANCELLED`.
