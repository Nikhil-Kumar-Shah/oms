# RESOURCE RELATIONSHIPS & DATA COUPLING MODEL
## Paradox Sports Operations Management System (OMS)

**Document Status:** ARCHITECTURAL RELATIONSHIP & DEPENDENCY SPECIFICATION  
**Authoritative Stack:** FastAPI | SQLAlchemy 2.x | PostgreSQL 16+ | Pydantic v2  
**Verification Date:** September 1, 2026  

---

## 1. Relationship Classification Framework

To avoid tight architectural coupling or accidental circular dependencies, relationships between entities in Paradox Sports OMS are strictly categorized into four classes:

1. **OWNERSHIP (Hard Foreign Key + Lifecycle Binding):** The child entity cannot exist without its parent and shares its lifecycle (e.g. `Event` &rarr; `EventReadinessItem`, `Meeting` &rarr; `MeetingParticipant`, `Directive` &rarr; `DirectiveAcknowledgement`).
2. **DEPENDENCY (Hard Foreign Key + Scoping Validation):** The resource requires a valid parent entity to establish access boundaries, but maintains independent state (e.g. `Task` &rarr; `Vertical`, `DailyReport` &rarr; `User`).
3. **RELATIONSHIP (Optional Foreign Key):** An operational link between independent resources to provide context without locking lifecycles (e.g. `Task.event_id` &rarr; `Event.id`, `Meeting.event_id` &rarr; `Event.id`).
4. **REFERENCE (Loose Metadata / String / URL Link):** External links or references where no relational foreign key is enforced, preserving the external data boundary (e.g. `CommunicationLog.reference_link`, `Issue.evidence_link`, `CalendarEntry.resource_link`).

---

## 2. Comprehensive Resource Relationship Maps

### A. Task Relationship Model
```
Task (tasks)
 ├── [DEPENDENCY] vertical_id ───────► Vertical (verticals.id) [NOT NULL]
 ├── [DEPENDENCY] assigned_to_id ────► User (users.id) [NOT NULL]
 ├── [DEPENDENCY] assigned_by_id ────► User (users.id) [NULLABLE]
 ├── [RELATIONSHIP] event_id ────────► Event (events.id) [NULLABLE]
 ├── [OWNERSHIP] comments ───────────► TaskComment (task_comments.task_id) [1:N]
 ├── [OWNERSHIP] history ────────────► TaskHistory (task_history.task_id) [1:N]
 └── [REFERENCE] reference_link ─────► External Resource URL [TEXT]
```

### B. Event Relationship Model
```
Event (events)
 ├── [DEPENDENCY] vertical_id ───────► Vertical (verticals.id) [NOT NULL]
 ├── [DEPENDENCY] primary_poc_id ────► User (users.id) [NOT NULL]
 ├── [DEPENDENCY] event_head_id ─────► User (users.id) [NULLABLE]
 ├── [OWNERSHIP] team_members ───────► EventMember (event_members.event_id) [1:N]
 ├── [OWNERSHIP] readiness_items ────► EventReadinessItem (event_readiness_items.event_id) [1:8]
 ├── [RELATIONSHIP] linked_tasks ────► Task (tasks.event_id) [1:N]
 ├── [RELATIONSHIP] linked_meetings ─► Meeting (meetings.event_id) [1:N]
 └── [REFERENCE] document_link ──────► Rulebook / Poster External URL [TEXT]
```

### C. Meeting Relationship Model
```
Meeting (meetings)
 ├── [DEPENDENCY] organizer_id ──────► User (users.id) [NOT NULL]
 ├── [RELATIONSHIP] vertical_id ─────► Vertical (verticals.id) [NULLABLE]
 ├── [RELATIONSHIP] event_id ────────► Event (events.id) [NULLABLE]
 ├── [OWNERSHIP] participants ───────► MeetingParticipant (meeting_participants.meeting_id) [1:N]
 └── [REFERENCE] meeting_url ────────► Virtual Meeting Link (Google Meet/Teams) [TEXT]
```

### D. Requirement Relationship Model
```
Requirement (requirements)
 ├── [DEPENDENCY] requesting_vertical_id ──► Vertical (verticals.id) [NOT NULL]
 ├── [DEPENDENCY] target_vertical_id ──────► Vertical (verticals.id) [NOT NULL]
 ├── [DEPENDENCY] requester_id ────────────► User (users.id) [NOT NULL]
 ├── [DEPENDENCY] assignee_id ─────────────► User (users.id) [NULLABLE]
 ├── [RELATIONSHIP] event_id ──────────────► Event (events.id) [NULLABLE]
 └── [OWNERSHIP] messages ─────────────────► RequirementMessage (requirement_messages.requirement_id) [1:N]
```

### E. Advanced Form & Submission Model
```
Form (forms)
 ├── [DEPENDENCY] owner_id ──────────► User (users.id) [NOT NULL]
 ├── [RELATIONSHIP] vertical_id ─────► Vertical (verticals.id) [NULLABLE]
 ├── [OWNERSHIP] versions ───────────► FormVersion (form_versions.form_id) [1:N]
 └── [OWNERSHIP] submissions ────────► FormSubmission (form_submissions.form_id) [1:N]
                                       ├── [DEPENDENCY] submitter_id ──► User (users.id)
                                       ├── [DEPENDENCY] reviewer_id ───► User (users.id)
                                       └── [RELATIONSHIP] transformed_entity_id (Task/Event/Req/Issue)
```

### F. Directive & Acknowledgement Model
```
Directive (directives)
 ├── [DEPENDENCY] issued_by_id ──────► User (users.id) [NOT NULL]
 ├── [RELATIONSHIP] vertical_id ─────► Vertical (verticals.id) [NULLABLE]
 ├── [RELATIONSHIP] target_user_id ──► User (users.id) [NULLABLE]
 └── [OWNERSHIP] acknowledgements ───► DirectiveAcknowledgement (directive_acknowledgements.directive_id) [1:N]
                                       └── [DEPENDENCY] user_id ──► User (users.id)
```

---

## 3. Lifecycle Dependencies & Constraints

1. **User Deactivation Impact:**
   - When a user is marked `AccountStatus.DISABLED`, all active tasks assigned to the user remain in their current state but become flagged for supervisor reassignment or ownership transfer.
   - Tasks and reports are **never** cascade-deleted.
2. **Vertical Archival Impact:**
   - When a vertical is archived (`VerticalStatus.ARCHIVED`), no new tasks, events, or reports can be created under it. Historical records remain fully queryable for audit and reporting.
3. **Event Completion Impact:**
   - When an event moves to `COMPLETED`, linked tasks and meetings maintain their independent statuses. Event readiness checkpoints are locked.
4. **Form Version Immutability:**
   - Publishing a form version prevents any modification to that version's schema. New requirements require incrementing to a new version.
