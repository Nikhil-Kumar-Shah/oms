# Phase 4 — Event & Coordination System Specification

**Project:** Paradox Sports OMS  
**Architecture:** FastAPI + SQLAlchemy 2.0 + PostgreSQL  
**Status:** COMPLETE & AUTHORITATIVE  

---

## 1. Architectural Philosophy & Integrity Rules

1. **PostgreSQL as Single Authoritative Truth:** All operations (events, rosters, checklists, cross-vertical requirements, meetings, forms, versions, and submissions) are transactionally written to PostgreSQL with strict relational integrity.
2. **Strict Organizational Hierarchy:** `Organization -> Vertical -> User`. No "Department" abstraction is used in models, routes, schemas, or templates.
3. **Zero Hard Deletion Policy:** Operational resources are permanent records. Deletion is managed strictly through lifecycle state transitions (`ARCHIVED`, `CANCELLED`, `REJECTED`). Normal API operations do not provide HTTP `DELETE` methods (returns `405 Method Not Allowed`).
4. **Structured Forms as Transformation Pipelines:** Advanced Forms are not basic survey collections; they are version-controlled, schema-validated entry mechanisms that automatically transform into authoritative PostgreSQL operational entities (`Task`, `Requirement`, `Event`) upon supervisor approval.
5. **Separation of Concerns & External Dataset Policy:** High-volume participant registries, tournament brackets, and poster assets are stored via external links (`resource_links`, `evidence_link`, `meeting_url`). OMS stores reference links and operational metadata only.

---

## 2. Relational Schema & Models

### 2.1 Events & Readiness
- `events`: Central operational events table with type enum (`TOURNAMENT`, `MATCH`, `TRAINING`, `CEREMONY`, `SELECTION_TRIAL`, `OTHER`), planned date, start/end times, venue location, society name, event head, and primary POC foreign keys.
- `event_members`: Event operational team roster with native role enums (`HEAD`, `COORDINATOR`, `LOGISTICS_LEAD`, `TECHNICAL_OFFICIAL`, `VOLUNTEER`, `MEMBER`).
- `event_readiness_items`: Structured checklist checkpoints automatically initialized upon event creation across categories (`PLANNING`, `COORDINATION`, `TECHNICAL_PREPARATION`, `LOGISTICS_SUPPLY`, `VENUE_FACILITY`, `PROMOTION_OUTREACH`, `SECURITY_SAFETY`, `POST_EVENT_WRAPUP`).

### 2.2 Cross-Vertical Requirements
- `requirements`: Explicit cross-division requests routing from `requesting_vertical_id` to `target_vertical_id`. Validates that any designated assignee is an active member of the target vertical.
- `requirement_messages`: Chronological audit and discussion thread attached to requirements.

### 2.3 Operational Meetings
- `meetings`: Operational meetings linked optionally to a vertical and/or event.
- `meeting_participants`: Participant roster with RSVP tracking (`PENDING`, `ACCEPTED`, `DECLINED`, `TENTATIVE`). Rescheduling atomically resets non-organizer RSVPs to `PENDING`.

### 2.4 Advanced Forms & Transformations
- `forms`: Root form definition specifying name, purpose, vertical scope, target audience (`ORGANIZATION`, `VERTICAL`, `PUBLIC`), and current version number.
- `form_versions`: Immutable version snapshots storing authoritative JSON `schema` and `transformation_config`. Publishing a version freezes it permanently from in-place edits.
- `form_submissions`: Submissions validated strictly against the published version schema. Supports supervisor review with strict self-approval prevention (`submitter_id != reviewer_id`).

---

## 3. Endpoints Matrix

| Endpoint | Method | Required Permission | Description |
|---|---|---|---|
| `/api/v1/events` | GET | `events.read` | List operational events with filters |
| `/api/v1/events` | POST | `events.create` | Create event and auto-initialize 8 readiness items |
| `/api/v1/events/{id}` | GET | `events.read` | Get event details |
| `/api/v1/events/{id}` | PATCH | `events.update` | Update event metadata |
| `/api/v1/events/{id}/transition` | POST | `events.transition` | Transition event lifecycle status |
| `/api/v1/events/{id}/poc` | POST | `events.team.manage` | Designate primary POC |
| `/api/v1/events/{id}/team` | GET | `events.read` | List event roster |
| `/api/v1/events/{id}/team` | POST | `events.team.manage` | Add member to event team |
| `/api/v1/events/{id}/readiness` | GET | `events.read` | List event readiness checkpoints |
| `/api/v1/events/{id}/readiness/{item_id}` | PATCH | `events.readiness.manage` | Update readiness item status & evidence |
| `/api/v1/events/{id}/dashboard` | GET | `events.read` | Aggregated operational dashboard query |
| `/api/v1/requirements` | GET | `requirements.read` | List cross-vertical requirements |
| `/api/v1/requirements` | POST | `requirements.create` | Raise cross-vertical requirement |
| `/api/v1/requirements/{id}/assign` | POST | `requirements.assign` | Assign to target vertical member |
| `/api/v1/requirements/{id}/transition` | POST | `requirements.transition` | Transition requirement status |
| `/api/v1/requirements/{id}/messages` | GET/POST | `requirements.read` / `requirements.message` | List / Post contextual messages |
| `/api/v1/meetings` | GET / POST | `meetings.read` / `meetings.create` | List / Schedule meetings |
| `/api/v1/meetings/{id}/rsvp` | POST | `meetings.rsvp` | Submit participant RSVP |
| `/api/v1/meetings/{id}/reschedule` | POST | `meetings.update` | Reschedule meeting with audit reset |
| `/api/v1/forms` | GET / POST | `forms.read` / `forms.create` | List / Create structured forms |
| `/api/v1/forms/{id}/publish` | POST | `forms.publish` | Publish immutable form version |
| `/api/v1/forms/{id}/submissions` | GET / POST | `forms.read` / `forms.submit` | List / Submit form responses |
| `/api/v1/form-submissions/{id}/review` | POST | `forms.review` | Review submission & trigger structured transformation |

---

## 4. Verification Summary

- **Automated Tests:** 77/77 tests passed across all Phase 1–4 suites.
- **Security Defenses Verified:**
  - Self-approval prohibition on form review enforced (403 Forbidden).
  - Cross-vertical team and requirement assignment boundaries enforced (422).
  - Zero hard-deletion policy verified (405 Method Not Allowed on all DELETE operations).
- **PostgreSQL Persistence:** Verified across independent raw SQL query sessions.
