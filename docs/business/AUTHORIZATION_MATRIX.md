# Authorization & RBAC Matrix
**Paradox Sports Operations Management System (OMS)**

## 1. Canonical Roles Overview

| Role Code | Role Name | Scope & Authority |
| :--- | :--- | :--- |
| `ADMIN` | System Administrator | Unrestricted system-wide operational, administrative, and configuration authority. |
| `SPORTS_CORE` | Sports Core Executive | Executive operational leadership across all verticals. Directives, approvals, executive analytics. |
| `DEPUTY_CORE` | Deputy Core Executive | Deputy operational leadership with broad cross-vertical supervisory authority. |
| `SUPER_COORDINATOR`| Super Coordinator | Cross-vertical operations coordinator managing multi-vertical workflows and requirements. |
| `COORDINATOR` | Vertical Coordinator | Operational head of a specific vertical division. Task assignment, report review, event rosters. |
| `VOLUNTEER` | Operational Volunteer | Vertical operational member. Task execution, report submission, checklist completion. |
| `EVENT_TEAM` | Event Team Member | Designated event team member for specific tournament or fixture operations. |

---

## 2. Resource × Role × Action Matrix

| Resource | Role | View | Create | Edit | Assign | Approve | Reject | Archive | Escalate | Administer |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Users** | `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| | `VOLUNTEER` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| **Verticals** | `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | — | ❌ |
| | `COORDINATOR` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ (Assigned) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| **Tasks** | `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| | `SUPER_COORDINATOR` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ (Vertical) | ✅ (Vertical) | ✅ (Vertical) | ✅ | ✅ | ✅ | ✅ | ❌ |
| | `VOLUNTEER` | ✅ (Assigned) | ❌ | ✅ (Status/Progress) | ❌ | ❌ | ❌ | ❌ | ✅ (Block) | ❌ |
| | `EVENT_TEAM` | ✅ (Assigned) | ❌ | ✅ (Status/Progress) | ❌ | ❌ | ❌ | ❌ | ✅ (Block) | ❌ |
| **My Work** | *Authenticated User* | ✅ (Self) | ❌ | ✅ (Progress) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Master Calendar** | `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ | ✅ (Vertical) | ✅ (Vertical) | — | ❌ | — | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ | ❌ | ❌ | — | ❌ | — | ❌ | — | ❌ |
| **Issues** | `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ | ✅ (Vertical) | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| | `VOLUNTEER` | ✅ (Vertical/Non-Conf) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Daily Reports** | `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ (Non-Self) | ✅ | — | — | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ | ✅ (Self) | — | ✅ (Non-Self) | ✅ | — | — | ❌ |
| | `VOLUNTEER` | ✅ (Self) | ✅ | ✅ (Draft) | — | ❌ | ❌ | — | — | ❌ |
| **Events** | `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ (Vertical) | ✅ (Vertical) | ✅ (Team) | ❌ | ❌ | ❌ | — | ❌ |
| | `EVENT_TEAM` | ✅ (Assigned) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| **Requirements**| `ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| | `SUPER_COORDINATOR`| ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ | ✅ (Vertical) | ✅ (Target) | ✅ | ✅ | ❌ | ✅ | ❌ |
| | `VOLUNTEER` | ✅ (Vertical) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Meetings** | `ADMIN` | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ | ✅ (Vertical) | ✅ (Organizer) | — | — | — | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ (Invited) | ❌ | ❌ | — | — | — | ❌ | — | ❌ |
| **Forms** | `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ | ✅ (Vertical) | ✅ (Draft) | — | ✅ (Submissions) | ✅ | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ (Published) | ❌ (Submit only) | ❌ | — | ❌ | ❌ | ❌ | — | ❌ |
| **Announcements**| `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ | ✅ (Vertical) | ✅ (Draft) | — | ❌ | — | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ (Audience) | ❌ | ❌ | — | ❌ | — | ❌ | — | ❌ |
| **Directives** | `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ (Vertical) | ✅ (Draft) | — | ❌ | — | ❌ | — | ❌ |
| | `VOLUNTEER` | ✅ (Assigned) | ❌ | ❌ | — | ❌ | — | ❌ | — | ❌ |
| **Transfers** | `ADMIN` | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — | ✅ |
| | `SPORTS_CORE` | ✅ | ✅ | ✅ | — | ✅ (Non-Self) | ✅ | — | — | ❌ |
| | `COORDINATOR` | ✅ (Vertical) | ✅ (Owned) | ❌ | — | ✅ (Non-Self) | ✅ | — | — | ❌ |
| **Audit Logs** | `ADMIN` | ✅ | ❌ (Auto) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (Immutable) |
| | `SPORTS_CORE` | ✅ | ❌ (Auto) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **System Config**| `ADMIN` | ✅ | ✅ | ✅ | — | — | — | — | — | ✅ |
