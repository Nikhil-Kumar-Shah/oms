# POLICY DECISION REGISTER
## Paradox Sports Operations Management System (OMS)

**Document Status:** OPEN GOVERNANCE & BUSINESS POLICY DECISION REGISTER  
**Authoritative Stack:** FastAPI | SQLAlchemy 2.x | PostgreSQL 16+ | Pydantic v2  
**Verification Date:** September 1, 2026  

---

## 1. Open Governance Decisions

This register documents every operational rule, business policy, or workflow behavior that requires executive stakeholder decision before subsequent feature expansion.

---

### Policy 01: Organization-Wide Tasks
- **Status:** `OPEN DECISION`
- **Question:** Can a Master Task exist at the top-level `ORGANIZATION` scope without being bound to a specific vertical division?
- **Option A (Current Behavior):** Strictly **NO**. Every task must belong to a vertical division to ensure direct accountability. Cross-cutting tasks belong to an executive vertical (e.g. `Executive Management` or `Central Coordination`).
- **Option B:** **YES**. Allow `vertical_id` to be nullable for top-level organization tasks assigned directly by `ADMIN` or `SPORTS_CORE`.
- **Recommendation:** **Option A**. Preserves strict vertical data isolation and prevents orphaned, unowned tasks.

---

### Policy 02: Multi-Owner Task Assignments
- **Status:** `OPEN DECISION`
- **Question:** Should a Master Task support multiple assignees or strictly maintain a single owner?
- **Option A (Current Behavior):** Strictly **SINGLE OWNER** (`assigned_to_id`). A task represents individual operational accountability. Collaborative efforts should be decomposed into sub-tasks or cross-vertical requirements.
- **Option B:** **MULTI-OWNER**. Introduce a `task_assignees` junction table allowing multiple users to be assigned to one task.
- **Recommendation:** **Option A**. Single ownership prevents diffusion of responsibility and ambiguity in progress reporting.

---

### Policy 03: Reopening Completed Tasks
- **Status:** `OPEN DECISION`
- **Question:** Can a task in `COMPLETED` status be transitioned back to `IN_PROGRESS` or `NOT_STARTED`?
- **Option A (Current Behavior):** **NO**. Once marked `COMPLETED` and audited, a task is terminal. If additional work is needed, a follow-up task should be created with a reference link.
- **Option B:** **SUPERVISOR ONLY**. Allow `COORDINATOR` or `ADMIN` to reopen a completed task with a mandatory reason note logged to `task_history`.
- **Recommendation:** **Option B**. Provides operational flexibility when QA checks reveal incomplete field work.

---

### Policy 04: Master Calendar Creation Permissions
- **Status:** `OPEN DECISION`
- **Question:** Who is authorized to create entries in the Master Calendar?
- **Option A (Current Behavior):** `ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`. Volunteers can view but not create calendar entries.
- **Option B:** All roles (including `VOLUNTEER`) can propose entries that require coordinator approval.
- **Recommendation:** **Option A**. Keeps the master schedule curated, accurate, and free of clutter.

---

### Policy 05: Task Lifecycle on User Disabling
- **Status:** `OPEN DECISION`
- **Question:** What should happen to active tasks assigned to a user when their account is marked `AccountStatus.DISABLED`?
- **Option A (Current Behavior):** Tasks remain in their current state (`IN_PROGRESS`/`BLOCKED`), but an alert is triggered in the Coordinator's dashboard to reassign the task via Ownership Transfer.
- **Option B:** Server automatically reassigns all active tasks to the user's primary vertical Coordinator.
- **Recommendation:** **Option A**. Gives supervisors explicit review over pending work before manual reassignment.

---

### Policy 06: Independent Events Without Verticals
- **Status:** `OPEN DECISION`
- **Question:** Can an Event exist independently without belonging to a primary vertical division?
- **Option A (Current Behavior):** Strictly **NO**. Every event has a primary host vertical (`vertical_id`), even if other verticals provide supporting event team members.
- **Option B:** **YES**. Events can be organization-level entities managed directly by `SPORTS_CORE`.
- **Recommendation:** **Option A**. Host vertical ownership guarantees logistical accountability for budget and venue.

---

### Policy 07: Weekly Report Generation Method
- **Status:** `OPEN DECISION`
- **Question:** How should Weekly Reports be structured and compiled?
- **Option A (Automated Rollup):** Server generates automated weekly dashboard aggregating approved Daily Reports and closed tasks within a date window.
- **Option B (Structured Form Submission):** Coordinators fill out a dedicated weekly qualitative synthesis form via the Forms Engine.
- **Option C (Hybrid):** Auto-generated numerical rollup pre-populated with coordinator qualitative commentary.
- **Recommendation:** **Option C (Hybrid)**. Combines automated data truth with human operational context.

---

### Policy 08: Resources Requiring Formal Supervisor Approval
- **Status:** `OPEN DECISION`
- **Question:** Which operational lifecycle transitions strictly require independent multi-party approval?
- **Current Canonical Policy:**
  1. **Daily Work Reports:** Must be reviewed and approved by Coordinator (`status = REVIEWED`). Submitter self-review strictly blocked (403).
  2. **Form Submissions:** Must be approved by Coordinator/Admin to trigger entity transformation. Submitter self-approval strictly blocked (403).
  3. **Ownership Transfers:** Must be approved by Supervisor to reassign Task/Event/Requirement. Requester self-approval strictly blocked (403).
  4. **Event Readiness Checkpoints:** Must be signed off by designated Event POC / Head.
- **Recommendation:** **Maintain all 4 approval gates**. Essential for fraud prevention and operational integrity.

---

## 2. Policy Implementation Tracking Summary

| Policy ID | Area | Current Status | Impact on Schema | Action Required |
|---|---|---|---|---|
| **POL-01** | Org Tasks | Open Decision | None (Enforce in Service) | Awaiting Executive Sign-Off |
| **POL-02** | Multi-Owner Tasks | Open Decision | None (Single Owner Maintained) | Awaiting Executive Sign-Off |
| **POL-03** | Task Reopening | Open Decision | Service transition validator | Awaiting Executive Sign-Off |
| **POL-04** | Calendar Creation | Open Decision | None (RBAC Enforced) | Awaiting Executive Sign-Off |
| **POL-05** | User Disabling Action | Open Decision | Service notification hook | Awaiting Executive Sign-Off |
| **POL-06** | Org-Level Events | Open Decision | None (Vertical Scoped) | Awaiting Executive Sign-Off |
| **POL-07** | Weekly Reporting | Open Decision | Forms / Analytics view | Awaiting Executive Sign-Off |
| **POL-08** | Approval Gates | Open Decision | Four-eyes principle enforced | Awaiting Executive Sign-Off |
