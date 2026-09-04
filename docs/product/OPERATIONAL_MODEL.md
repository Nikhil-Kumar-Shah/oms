# OPERATIONAL MODEL SPECIFICATION
## Paradox Sports Operations Management System (OMS)

**Document Status:** CONCEPTUAL SPECIFICATION & ARCHITECTURAL MODEL  
**Authoritative Stack:** FastAPI | SQLAlchemy 2.x | PostgreSQL 16+ | Pydantic v2 | Jinja2  
**Verification Date:** September 1, 2026  

---

## 1. Organizational Model

The organizational model represents the institutional hierarchy of Paradox Sports.

```
┌────────────────────────────────────────────────────────────┐
│                    ORGANIZATION                            │
│           (Top-Level Sports Authority Domain)              │
└─────────────────────────────┬──────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│   VERTICAL DIVISION   │           │   VERTICAL DIVISION   │
│ (e.g. Football Ops)   │           │ (e.g. Logistics & Eq) │
└───────────┬───────────┘           └───────────┬───────────┘
            │                                   │
      ┌─────┴─────┐                       ┌─────┴─────┐
      ▼           ▼                       ▼           ▼
┌───────────┐ ┌───────────┐         ┌───────────┐ ┌───────────┐
│   USER    │ │   USER    │         │   USER    │ │   USER    │
│(Coord/Vol)│ │(Coord/Vol)│         │(Coord/Vol)│ │(Coord/Vol)│
└───────────┘ └───────────┘         └───────────┘ └───────────┘
```

- **Strict Invariant:** `Organization` &rarr; `Vertical` &rarr; `User`.
- **Zero Legacy Concepts:** The term and concept of "Department" is strictly abolished across all models, tables, routes, and UI.
- **Dynamic Verticals:** Stored in the `verticals` table. Verticals can be created, updated, disabled, and archived at runtime by Administrators without database schema migrations.
- **Multi-Vertical Assignments:** Users can belong to multiple verticals via the `user_verticals` junction table, with exactly one marked as `is_primary=True`.

---

## 2. Resource Scope Model

Resources within Paradox Sports OMS are scoped according to operational ownership and visibility needs:

| Scope Level | Scope Meaning | Representative Resources | Access Control Rule |
|---|---|---|---|
| **ORGANIZATION** | Global visibility across all verticals | Organization Announcements, Master Calendar (Org), System Configs, Administrative Analytics | Readable by all authenticated users; manageable by `ADMIN` / `SPORTS_CORE` / `DEPUTY_CORE`. |
| **VERTICAL** | Scoped strictly to members of that vertical division | Master Tasks, Daily Reports, Vertical Directives, Vertical Forms, Vertical Calendar | Accessible only by users assigned to that vertical division. |
| **USER** | Personal to the individual authenticated user | My Work dashboard, Personal Notifications, Directives targeted to User | Strictly private to the user identity extracted from server session. |
| **EVENT** | Bound to a specific athletic tournament or event | Event Readiness Checkpoints, Event Team Roster, Event-Linked Tasks, Event Meetings | Managed by Event Head / POC; visible to Event Team members. |
| **MEETING** | Bound to scheduled meeting instances | Participant Rosters, RSVPs, Meeting Minutes, Action Items | Accessible by organizer and invited participants. |
| **MULTI-SCOPE** | Connecting two distinct verticals | Cross-Vertical Requirements (`source_vertical_id` &rarr; `target_vertical_id`) | Shared visibility between requesting and fulfilling vertical members. |

---

## 3. User & Identity Model

- **Authentication:** Server-authoritative credentials validated against `Argon2id` / `bcrypt` hashes.
- **Session Tokens:** High-entropy cryptographically random session tokens stored in `user_sessions` with IP address, user-agent, and expiration timestamps.
- **Account Lifecycles:**
  - `ACTIVE`: Normal operational state.
  - `DISABLED`: Suspended state. Triggers immediate session revocation and login block.
  - `LOCKED`: Temporary lockout after repeated authentication failures.
- **Zero Hard Deletion:** User records are never hard-deleted; historical ownership and audit logs remain intact.

---

## 4. Master Task Model

The primary operational unit of work.

- **Ownership Invariant:** Every task has exactly **one primary assignee** (`assigned_to_id`) within the task's vertical division.
- **Health Engine:**
  - `ON_TRACK`: Progress normal, deadline ahead.
  - `AT_RISK`: Deadline approaching within 48h with progress < 50%.
  - `BLOCKED`: Explicit blocker declared with reason string.
  - `CRITICAL`: Past deadline with progress < 100%.
- **Blocker Handling:** Any team member can flag a blocker with remarks. Marking a task as `BLOCKED` automatically alerts vertical coordinators.

---

## 5. Master Calendar Model

Aggregates all time-sensitive operational milestones.

- **Entry Types:**
  - `HARD_DEADLINE`: Operational hard stop (e.g. Budget submission, Venue payment).
  - `SOFT_DEADLINE`: Flexible internal milestone (e.g. Draft schedule review).
  - `EVENT_DATE`: Match or tournament fixture.
  - `MEETING_DATE`: Scheduled sync or briefing.
  - `INFORMATIONAL`: General calendar marker.
- **Audience Filtering:** Supports `ORGANIZATION`, `VERTICAL`, or `EVENT` audience filtering.

---

## 6. Event Coordination & Readiness Model

Events are high-level operational coordination anchors decoupled from internal task execution.

- **8 Canonical Readiness Checkpoints:**
  1. `VENUE_BOOKING` (Facility reservation, permits)
  2. `EQUIPMENT_CHECK` (Balls, nets, scoreboards, safety padding)
  3. `MEDICAL_STANDBY` (First aid team, emergency transport)
  4. `SECURITY_CLEARANCE` (Crowd management, access passes)
  5. `OFFICIALS_ASSIGNMENT` (Referees, umpires, timekeepers)
  6. `SCHEDULE_PUBLISHED` (Fixture brackets released)
  7. `HOSPITALITY_READY` (Refreshments, VIP & athlete amenities)
  8. `CONTINGENCY_PLAN` (Inclement weather / backup facilities)
- **Lifecycle:** `PLANNING` &rarr; `READY` &rarr; `IN_PROGRESS` &rarr; `COMPLETED` &rarr; `ARCHIVED`.

---

## 7. Meeting & Action Log Model

Coordinates operational alignment sessions.

- **Structure:** `Meeting` &rarr; multiple `MeetingParticipant` records.
- **RSVP Tracking:** `PENDING`, `ACCEPTED`, `DECLINED`, `TENTATIVE`.
- **Rescheduling / Cancellation:** Audited with required remarks string.

---

## 8. Issue & Escalation Model

Captures operational friction, rule violations, and emergencies.

- **Sensitivity Levels:**
  - `NORMAL`: Visible to all vertical members.
  - `SENSITIVE`: Restricted to coordinators and supervisors.
  - `CONFIDENTIAL`: Restricted to creator, assignee, and `ADMIN` (IDOR protected).
- **Escalation Path:** Allows vertical coordinators to escalate directly to `SPORTS_CORE` or `ADMIN` with required action summary.

---

## 9. Reporting Model (Daily & Weekly)

- **Daily Work Reports:**
  - Submitted daily by field coordinators and volunteers.
  - Unique constraint: exactly one report per user per vertical per date.
  - **Self-Review Prevention (403):** Submitter cannot approve own report.
  - **Post-Review Immutability:** Once reviewed, report content is locked.
- **Weekly Reporting:** Aggregated operational summary generated across daily reports and active tasks for executive review.

---

## 10. Communication Taxonomy Model

Strict separation of communication concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                   COMMUNICATION TAXONOMY                    │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │                
┌──────▼───────┐   ┌──────▼───────┐   ┌──────▼───────┐ ┌──────▼───────┐
│ ANNOUNCEMENT │   │  DIRECTIVE   │   │ NOTIFICATION │ │  COMM. LOG   │
│ (Broadcast)  │   │ (Mandatory)  │   │  (Attention) │ │  (Tracker)   │
└──────────────┘   └──────────────┘   └──────────────┘ └──────────────┘
```

1. **Announcements:** Informational notices with scope filtering.
2. **Directives:** Mandatory policy instructions with auto-generated individual compliance acknowledgement rosters.
3. **Notifications:** System alerts for assignments, blockers, and mentions.
4. **Communication Logs:** Formal records of external phone calls, emails, and notices with third parties.

---

## 11. Advanced Form & Transformation Model

- **Configurable JSON Schemas:** Field types (`TEXT`, `LONG_TEXT`, `NUMBER`, `BOOLEAN`, `DATE`, `SELECT`, `USER_REF`, `VERTICAL_REF`) and validation rules.
- **Version Immutability:** Form versions are locked upon publishing.
- **Transactional Transformation:** Approved submissions atomically generate native OMS records (`TASK`, `EVENT`, `REQUIREMENT`, `ISSUE`).

---

## 12. Governance & Ownership Transfer Model

- **Handover Workflow:** Supervised reassignment of Tasks, Events, and Requirements.
- **Anti-Fraud Control:** Requester cannot self-approve transfer requests. Target owner must exist and belong to the resource's vertical division.

---

## 13. Audit & Compliance Model

- **Tamper-Proof Audit Trail:** Append-only `audit_logs` capturing `actor_id`, `action`, `resource_type`, `resource_id`, `outcome`, `timestamp`, and `details`.
- **External Data Boundary:** OMS does NOT store large participant datasets, raw spreadsheets, or high-res media. The system stores metadata + reference URLs.
