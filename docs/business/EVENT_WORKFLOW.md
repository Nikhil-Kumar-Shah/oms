# Event Coordination & Readiness Workflow
**Paradox Sports Operations Management System (OMS)**

## 1. Architectural Boundary: Events vs Internal Operational Work

In Paradox Sports OMS, an **Event** is an umbrella operational milestone (tournament, match, ceremony, training workshop) that coordinates multiple vertical divisions.

> [!IMPORTANT]
> **Decoupling Rule**: Events are NOT a duplicate task-management system.
> - An **Event** contains high-level operational parameters, designated Points of Contact (POCs), an Event Team roster, and an 8-point **Readiness Checklist**.
> - Operational work items required for the event (e.g. "Prepare turf", "Order trophies", "Print banner") are created as standard **Master Tasks** or **Cross-Vertical Requirements** that link back to the event via `event_id` or `resource_links`.

---

## 2. Event Team Structure & Roles

Each event maintains a designated operational team (`event_members` table) with structured roles:
- **EVENT_HEAD**: Overall operational leader accountable for event execution and readiness sign-off.
- **PRIMARY_POC**: Primary Point of Contact for internal and external coordination queries.
- **COORDINATOR**: Vertical coordinator executing specific domain logistics (e.g., referee coordination).
- **VOLUNTEER**: Team members handling on-ground execution (e.g., scorekeeping, water stations).
- **LOGISTICS_LEAD**: Equipment, venue, and material management head.
- **MEDIA_LEAD**: Photography, live streaming, and social media coverage head.

---

## 3. The 8 Default Readiness Checkpoints

Upon creation of any operational event, the system automatically initializes 8 standardized readiness items (`event_readiness_items` table):

| Checkpoint # | Category | Checkpoint Title | Verification Requirement |
| :---: | :--- | :--- | :--- |
| **1** | `PLANNING` | Event Concept & Operational Scope Signed Off | Objectives and venue confirmed |
| **2** | `COORDINATION` | Event Head & Primary POC Assigned | Lead coordinators designated and briefed |
| **3** | `DOCUMENTATION` | Schedule & Activity Timeline Prepared | Chronological itinerary drafted and approved |
| **4** | `COMMUNICATIONS` | Internal & External Communications Issued | Notices and briefings dispatched |
| **5** | `TECHNICAL_PREP` | Equipment & Venue Technical Prep | Scoreboards, hardware, turf/court verified |
| **6** | `MOCK_TRIAL` | Dry Run / Rehearsal Conducted | Operational rehearsal executed |
| **7** | `FINAL_APPROVAL` | Executive Core Leadership Sign-Off | Sports Core executive sign-off obtained |
| **8** | `EXECUTION_READY` | Event Day Operational Readiness Confirmed | All staff, emergency protocols deployed |

---

## 4. Aggregated Event Dashboard & Real-Time Analytics

The event service provides real-time aggregation across:
- **Readiness Progress**: Percentage of verified checkpoints (`verified_items / total_items * 100`).
- **Team Roster Count**: Number of assigned coordinators and volunteers.
- **Linked Task Completion**: Number of linked master tasks in `COMPLETED` status vs `BLOCKED` or `IN_PROGRESS`.
- **Linked Requirements**: Status of inbound cross-vertical requests for this event.

---

## 5. Event Lifecycle Transitions

1. **PLANNING**: Concept created, team assembled, readiness checkpoints progressing.
2. **IN_PROGRESS**: Event day underway, on-ground operations active.
3. **COMPLETED**: Tournament concluded, scores verified, trophies presented.
4. **ARCHIVED**: Event archived for historical record and seasonal reporting.
