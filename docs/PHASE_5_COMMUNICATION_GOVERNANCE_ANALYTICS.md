# Phase 5 — Communication, Governance & Analytics Specification
**Paradox Sports Operations Management System (OMS)**

## 1. Overview & Architecture

Phase 5 establishes the authoritative communication, governance, and operational intelligence layer of the Paradox Sports OMS platform. It complements the existing foundational, identity, operational, and event coordination layers with:
- **Announcements & Broadcasts**: Informational broadcasting scoped to the Organization, Vertical Divisions, or targeted personnel with automated notification dispatch.
- **Directives & Governance Compliance**: Binding operational instructions requiring individual user acknowledgement rosters, tracking compliance timestamps and notes.
- **Attention & Notification Engine**: Server-authoritative notifications alerting personnel to tasks, directives, announcements, meetings, and transfer requests with strict IDOR isolation.
- **Official Communication Tracker**: Structured audit ledger for external and operational communications (letters, permissions, key notices, critical phone calls).
- **Resource Ownership Transfers**: Governed handoff protocol for Tasks, Events, and Requirements enforcing vertical eligibility, self-approval blockage, and atomic transactional resource mutation.
- **Immutable Audit Center & System Configuration**: System-wide configuration repository with typed validation (zero secrets in DB) and chronological audit search.
- **Operational Intelligence & Administrative Analytics**: High-performance SQL aggregate calculations across all system domains without pulling raw tables into memory.

---

## 2. PostgreSQL Schema & Entity Models

### A. Communication Models (`app/models/communication.py`)
1. `announcements`:
   - `id`, `title`, `content`, `category`, `priority` (`LOW`, `NORMAL`, `HIGH`, `URGENT`), `scope` (`ALL`, `VERTICAL`, `USER`), `vertical_id`, `target_user_id`, `author_id`, `status` (`DRAFT`, `PUBLISHED`, `ARCHIVED`), `published_at`, `expires_at`, `archived_at`.
2. `directives`:
   - `id`, `title`, `instruction`, `issued_by_id`, `scope`, `vertical_id`, `target_user_id`, `priority`, `effective_date`, `deadline`, `status` (`DRAFT`, `ISSUED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `ARCHIVED`), `requires_acknowledgement`.
3. `directive_acknowledgements`:
   - `id`, `directive_id`, `user_id`, `status` (`PENDING`, `ACKNOWLEDGED`), `acknowledged_at`, `notes`.
   - Unique Constraint: `(directive_id, user_id)`.
4. `notifications`:
   - `id`, `recipient_id`, `notification_type` (`SYSTEM`, `TASK`, `DIRECTIVE`, `ANNOUNCEMENT`, `MEETING`, `REPORT`, `TRANSFER`, `FORM`), `title`, `message`, `related_resource_type`, `related_resource_id`, `read_status` (`UNREAD`, `READ`, `DISMISSED`), `read_at`.
5. `communication_logs`:
   - `id`, `date_time`, `communication_type` (`CALL`, `EMAIL`, `OFFICIAL_MESSAGE`, `LETTER`, `OTHER`), `subject`, `sender_info`, `recipient_info`, `vertical_id`, `related_resource_type`, `related_resource_id`, `reference_link`, `remarks`, `created_by_id`, `status` (`RECORDED`, `ARCHIVED`).

### B. Governance Models (`app/models/governance.py`)
1. `ownership_transfers`:
   - `id`, `resource_type` (`EVENT`, `TASK`, `REQUIREMENT`), `resource_id`, `current_owner_id`, `requested_owner_id`, `requested_by_id`, `reviewed_by_id`, `reason`, `status` (`PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`, `COMPLETED`), `remarks`, `reviewed_at`, `completed_at`.
2. `system_configs`:
   - `id`, `key` (unique), `value`, `value_type` (`STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `JSON`), `description`, `is_active`, `updated_by_id`, `updated_at`.

---

## 3. RBAC Permissions Registry

The following server-authoritative permissions govern Phase 5 capabilities:
- **Announcements**: `announcements.read`, `announcements.create`, `announcements.update`, `announcements.publish`, `announcements.archive`
- **Directives & Compliance**: `directives.read`, `directives.create`, `directives.update`, `directives.issue`, `directives.acknowledge`
- **Notifications**: `notifications.read`, `notifications.manage`
- **Communication Tracker**: `communications.read`, `communications.create`, `communications.update`
- **Ownership Transfers**: `transfers.read`, `transfers.request`, `transfers.approve`
- **System Configuration**: `config.read`, `config.update`
- **Analytics & Admin Reporting**: `analytics.read`, `analytics.admin`, `reports.admin`

---

## 4. API Endpoints Reference

| Method | Path | Summary | Permission |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/announcements` | List scoped announcements | `announcements.read` |
| `POST` | `/api/v1/announcements` | Draft or publish announcement | `announcements.create` |
| `POST` | `/api/v1/announcements/{id}/publish` | Publish announcement & trigger notifications | `announcements.publish` |
| `POST` | `/api/v1/announcements/{id}/archive` | Archive announcement | `announcements.archive` |
| `GET` | `/api/v1/directives` | List scoped directives | `directives.read` |
| `POST` | `/api/v1/directives` | Create directive | `directives.create` |
| `POST` | `/api/v1/directives/{id}/issue` | Issue directive & build acknowledgement roster | `directives.issue` |
| `POST` | `/api/v1/directives/{id}/acknowledge` | Acknowledge & sign directive | `directives.acknowledge` |
| `GET` | `/api/v1/notifications` | List user attention notifications | `notifications.read` |
| `POST` | `/api/v1/notifications/{id}/read` | Mark single notification as read | `notifications.manage` |
| `POST` | `/api/v1/notifications/read-all` | Mark all notifications as read | `notifications.manage` |
| `POST` | `/api/v1/notifications/{id}/dismiss` | Dismiss notification | `notifications.manage` |
| `GET` | `/api/v1/communications` | List official communications | `communications.read` |
| `POST` | `/api/v1/communications` | Record official communication | `communications.create` |
| `GET` | `/api/v1/transfers` | List ownership transfer requests | `transfers.read` |
| `POST` | `/api/v1/transfers` | Request resource ownership transfer | `transfers.request` |
| `POST` | `/api/v1/transfers/{id}/review` | Approve/reject ownership transfer | `transfers.approve` |
| `GET` | `/api/v1/admin/config` | List typed system configurations | `config.read` |
| `POST` | `/api/v1/admin/config` | Create configuration parameter | `config.update` |
| `PATCH` | `/api/v1/admin/config/{key}` | Update configuration parameter | `config.update` |
| `GET` | `/api/v1/analytics/operational` | Multi-metric vertical operational analytics | `analytics.read` |
| `GET` | `/api/v1/analytics/administrative` | System-wide executive analytics | `analytics.admin` |
| `GET` | `/api/v1/analytics/my-summary` | Personal workload & alert summary | `analytics.read` |
| `GET` | `/api/v1/admin/reports/{type}` | Tabular administrative operational reports | `reports.admin` |

---

## 5. Development Verification Interfaces

Access the following Jinja2 verification views in development:
- `/dev/announcements` — Broadcast creation and published feeds
- `/dev/directives` — Directive issuance and interactive acknowledgement roster
- `/dev/notifications` — Personal notifications roster and mark-read controls
- `/dev/communications` — Official communication log register
- `/dev/transfers` — Ownership transfer requests, self-approval prevention, supervisor approval
- `/dev/audit` — Immutable chronological audit search center
- `/dev/config` — System configuration key-value repository
- `/dev/health` — FastAPI runtime & PostgreSQL connection pool diagnostics
- `/dev/analytics` — Executive and vertical operational analytics dashboards
- `/dev/admin-reports` — Administrative reporting hub (Tasks, Events, Issues, Meetings)
