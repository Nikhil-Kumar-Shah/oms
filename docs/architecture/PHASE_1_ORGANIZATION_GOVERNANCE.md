# Phase 1: Organization + People + Role Governance Architecture

**System:** Paradox Sports Operations Management System (OMS)  
**Authoritative Reference:** `PRODUCT_SPECIFICATION.md`  
**Status:** Completed & 100% Acceptance Verified

---

## 1. Executive Summary

Phase 1 establishes the operational organizational foundation, canonical roles, people governance, and security isolation model for the Paradox Sports Operations Management System. 

It guarantees:
1. **Strict Hierarchy**: `Organization -> Vertical -> User` (Strictly **zero** department concept).
2. **Canonical 7 Roles**: `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`, `VOLUNTEER`, `EVENT_TEAM`.
3. **Internal vs. Event Team Account Separation**: Internal users manage and coordinate operations; Event Team users operate strictly within an isolated external boundary tied to their assigned `Event` via `EventTeamProfile`.
4. **POC Group Architecture**: Every active event is governed by an authoritative POC Group consisting of **exactly one active Head POC** (`primary_poc_id`) and designated POC members assigned to the event's vertical division.
5. **Multi-Tier Scoping & Isolation**: Strict server-authoritative enforcement across `USER_SCOPE`, `VERTICAL_SCOPE`, `EVENT_SCOPE`, and `ORGANIZATION_SCOPE`.

---

## 2. Organizational Model & Dynamic Vertical Lifecycle

### 2.1 Hierarchy
```
Organization (Paradox Sports Department)
  │
  ├── Vertical (Athletics) ──────── User (Coordinator / Volunteer)
  ├── Vertical (Football)  ──────── User (Super Coordinator / Coordinator)
  └── Vertical (Cricket)   ──────── User (Coordinator / Volunteer)
```

- **Organization**: Top-level root entity (`PARADOX_SPORTS`).
- **Vertical**: Dynamic operational grouping. Verticals are database-driven and managed via server-authoritative APIs.
- **No Department Concept**: Department entities, endpoints, terminology, or fields are strictly prohibited.

### 2.2 Vertical Lifecycle Transitions
- `ACTIVE`: Normal operations; users can be assigned, events created.
- `DISABLED`: Operational freeze; existing assignments remain, but new assignments/events are blocked.
- `ARCHIVED`: Historical record retention; read-only access.
- **Non-Destructive User Removal**: Users can be unassigned from a vertical via `DELETE /api/v1/admin/users/{user_id}/verticals/{vertical_id}` without deleting the user account.

---

## 3. Canonical 7 Roles & Role Capability Matrix

| Role | Scope | Key Capabilities | Prohibitions |
| :--- | :--- | :--- | :--- |
| **`ADMIN`** | Organization | Full system administration, user provisioning, vertical management, audit inspection. | None |
| **`SPORTS_CORE`** | Organization | Operational leadership across all verticals, event approval, POC assignment, directives. | Admin user password reset |
| **`DEPUTY_CORE`** | Organization | Operational leadership, cross-vertical coordination, readiness sign-offs. | Admin configuration overrides |
| **`SUPER_COORDINATOR`** | Vertical | Vertical lead; manages vertical tasks, coordinators, volunteers, event POCs, and team relations. | Cross-vertical management |
| **`COORDINATOR`** | Vertical | Operational coordinator; executes tasks, attends meetings, interacts with event POCs and teams. | Role management, vertical creation |
| **`VOLUNTEER`** | User / Vertical | Execution role; completes assigned tasks, logs daily reports, raises issues. | Approval, administrative actions |
| **`EVENT_TEAM`** | Event | Event-facing account; submits forms, views event details, updates team roster/contact info. | Internal discussions, audit, governance, other teams |

---

## 4. Internal User vs. Event Team User Separation

### 4.1 Internal User
- **Entity**: `User` + optional `UserProfile`
- **Role**: One of `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`, `VOLUNTEER`.
- **Association**: Assigned to one or more `Vertical` divisions.

### 4.2 Event Team Account & Profile
- **Entity**: `User` + `EventTeamProfile`
- **Role**: `EVENT_TEAM`
- **Relationship**: 1:1 with `User`, Foreign Key to `Event`.
- **Profile Fields**:
  - `team_name`: Official name of the participating team / society.
  - `head_name`, `head_email`, `head_phone`: Primary team contact.
  - `members_summary`: JSONB list of team participants.
  - `contact_info`: JSONB dict for emergency / coordinator contact info.
  - `event_metadata`: JSONB dict for event-specific registrations and gear requests.
  - `notes`: Operational notes.

---

## 5. POC Group Architecture

```
Event
 │
 └── POC Group
      ├── Head POC (Exactly 1 active User in Event's Vertical)
      ├── POC Member 1 (User in Event's Vertical)
      └── POC Member 2 (User in Event's Vertical)
```

- **Head POC**: Exactly one active lead POC per event (`event.primary_poc_id`).
- **POC Members**: Supporting coordinators from the vertical (`EventMemberRole.POC`).
- **Validation**: All designated POCs must have an active assignment in the target `Vertical`. Cross-vertical assignments are rejected (`HTTP 422`).

---

## 6. Security & Isolation Boundaries

1. **Internal Data Isolation**:
   - `EVENT_TEAM` users attempting to access `/api/v1/admin/users`, `/api/v1/admin/audit-logs`, or `/api/v1/organization/verticals` receive `HTTP 403 Forbidden`.
2. **Horizontal Team Isolation**:
   - `EVENT_TEAM` users attempting to view another event team's profile receive `HTTP 403 Forbidden`.
3. **Append-Only Audit Trail**:
   - Every sensitive organizational action (`VERTICAL_CREATE`, `VERTICAL_DISABLE`, `VERTICAL_ARCHIVE`, `VERTICAL_MEMBER_REMOVE`, `EVENT_TEAM_CREATE`, `EVENT_TEAM_UPDATE`, `EVENT_ASSIGN_POC_GROUP`) generates an immutable audit record.

---

## 7. Migration & Database Schema

- **Migration**: `migrations/versions/a1b2c3d4e5f6_phase1_organization_event_team_poc.py`
- **Table Created**: `event_team_profiles`
  - `id` (UUID PK)
  - `user_id` (UUID FK -> `users.id` on delete CASCADE, unique)
  - `event_id` (UUID FK -> `events.id` on delete CASCADE)
  - `team_name`, `head_name`, `head_email`, `head_phone`
  - `members_summary` (JSONB)
  - `contact_info` (JSONB)
  - `event_metadata` (JSONB)
  - `notes` (TEXT)
  - `created_at`, `updated_at` (TIMESTAMPTZ)

---

## 8. Verification Results

- **Automated Regression Suite**: 129 / 129 tests passing (100%).
- **Phase 1 Test Suite**: 7 / 7 tests passing (`tests/test_phase1_organization_people_governance.py`).
- **Standalone PostgreSQL E2E Verification**: 100% verified (`scripts/verify_phase1_governance.py`).
