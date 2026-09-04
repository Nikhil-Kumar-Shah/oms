# Phase 6 — Security, Performance & Production Specification
**Paradox Sports Operations Management System (OMS)**

## 1. Overview

Phase 6 completes the production readiness, security hardening, database query optimization, automated disaster recovery, and Azure VM deployment configuration for the Paradox Sports Operations Management System.

---

## 2. Security Hardening & Controls

### A. HTTP Production Security Headers
Every HTTP response issued by FastAPI carries mandatory standard security headers injected by `SecurityHeadersMiddleware`:
- `X-Content-Type-Options: nosniff` — Prevents MIME-sniffing vulnerabilities.
- `X-Frame-Options: DENY` — Prevents Clickjacking attacks in IFrames.
- `X-XSS-Protection: 1; mode=block` — Enables browser reflective XSS filter.
- `Referrer-Policy: strict-origin-when-cross-origin` — Protects referral path leaks.
- `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()` — Restricts hardware APIs.
- `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none';`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` — Enforces HTTPS in production.

### B. In-Memory Sliding-Window Rate Limiting
- **Authentication Protection**: Strict rate limit (10 requests/minute per client IP) on `/api/v1/auth/login`, `/dev/auth/login`, and `/api/v1/admin/users/{id}/reset-password`.
- **Global IP Throttle**: Rate limit (120 requests/minute per client IP) protecting application against excessive polling without external Redis.
- **Fail-Safe Response**: Returns standard `HTTP 429 Too Many Requests` with `Retry-After: <seconds>` header.

### C. CORS & Host Protection
- Configured via `CORS_ORIGINS` and `ALLOWED_HOSTS` in `Settings`.
- `TrustedHostMiddleware` blocks HTTP Host Header spoofing.

---

## 3. Database Composite Index Optimization

Alembic migration `e71a8bc43d12` adds 8 high-impact composite indexes to PostgreSQL:

| Index Name | Target Table | Indexed Columns | Query Acceleration |
| :--- | :--- | :--- | :--- |
| `idx_tasks_assigned_status` | `tasks` | `(assigned_to_id, status)` | Personal Work "My Work" list & badge |
| `idx_tasks_vertical_status` | `tasks` | `(vertical_id, status)` | Vertical Task Board & workload metrics |
| `idx_notifications_recipient_status_date` | `notifications` | `(recipient_id, read_status, created_at)` | Attention feed & unread notification counter |
| `idx_directives_vertical_status` | `directives` | `(vertical_id, status)` | Vertical directive compliance queue |
| `idx_events_vertical_date` | `events` | `(vertical_id, planned_date)` | Vertical event timelines & calendar |
| `idx_requirements_target_status` | `requirements` | `(target_vertical_id, status)` | Incoming vertical requirement queue |
| `idx_issues_vertical_sensitivity_status` | `issues` | `(vertical_id, sensitivity, status)` | Scoped confidential issue register |
| `idx_audit_logs_action_timestamp` | `audit_logs` | `(action, timestamp)` | Chronological audit center searches |

---

## 4. API Security Matrix

| Endpoint | Method | Authentication | Required Role/Permission | Object-Level Scope Check | Input Validation | Expected Unauthorized Response |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/auth/login` | POST | None | None | Rate Limited (10/min) | `LoginRequest` | 401 / 429 |
| `/api/v1/auth/logout` | POST | Bearer / Cookie | Any Valid Session | Valid Session | None | 401 |
| `/api/v1/auth/change-password` | POST | Bearer / Cookie | Any Valid Session | Valid Session | `PasswordChangeRequest` | 401 / 422 |
| `/api/v1/organization` | GET | Bearer / Cookie | Any Valid Session | None | None | 401 |
| `/api/v1/organization/verticals` | GET | Bearer / Cookie | Any Valid Session | None | None | 401 |
| `/api/v1/organization/verticals` | POST | Bearer / Cookie | `verticals.manage` | Admin Role | `VerticalCreate` | 401 / 403 |
| `/api/v1/admin/users` | GET / POST | Bearer / Cookie | `users.manage` | Admin Role | `UserCreate` | 401 / 403 |
| `/api/v1/my-work` | GET | Bearer / Cookie | Any Valid Session | Filtered by `current_user.id` | Query params | 401 |
| `/api/v1/tasks` | GET / POST | Bearer / Cookie | `tasks.read` / `tasks.create` | Vertical Assignment | `TaskCreate` | 401 / 403 |
| `/api/v1/tasks/{id}/transition` | POST | Bearer / Cookie | `tasks.transition` | Assignee / Supervisor | `TaskTransitionRequest` | 401 / 403 |
| `/api/v1/events` | GET / POST | Bearer / Cookie | `events.read` / `events.create` | Vertical Assignment | `EventCreate` | 401 / 403 |
| `/api/v1/events/{id}/team` | POST | Bearer / Cookie | `events.manage` | Vertical Eligibility | `EventMemberCreate` | 401 / 403 |
| `/api/v1/requirements` | GET / POST | Bearer / Cookie | `requirements.read` / `create` | Vertical Assignment | `RequirementCreate` | 401 / 403 |
| `/api/v1/meetings` | GET / POST | Bearer / Cookie | `meetings.read` / `create` | Vertical Assignment | `MeetingCreate` | 401 / 403 |
| `/api/v1/forms` | GET / POST | Bearer / Cookie | `forms.read` / `forms.create` | Vertical Assignment | `FormCreate` | 401 / 403 |
| `/api/v1/announcements` | GET / POST | Bearer / Cookie | `announcements.read` / `create`| Audience Scoping | `AnnouncementCreate` | 401 / 403 |
| `/api/v1/directives` | GET / POST | Bearer / Cookie | `directives.read` / `create` | Vertical Scoping | `DirectiveCreate` | 401 / 403 |
| `/api/v1/directives/{id}/acknowledge`| POST | Bearer / Cookie | `directives.acknowledge` | Target User Sign | `DirectiveAcknowledgeRequest` | 401 / 403 |
| `/api/v1/notifications` | GET | Bearer / Cookie | Any Valid Session | User Isolated IDOR | None | 401 |
| `/api/v1/notifications/{id}/read`| POST | Bearer / Cookie | Any Valid Session | User Isolated IDOR | None | 401 / 404 |
| `/api/v1/transfers` | GET / POST | Bearer / Cookie | `transfers.read` / `request` | Vertical Eligibility | `OwnershipTransferCreate` | 401 / 403 |
| `/api/v1/transfers/{id}/review` | POST | Bearer / Cookie | `transfers.approve` | No Self-Approval | `OwnershipTransferReviewRequest`| 401 / 403 |
| `/api/v1/analytics/operational` | GET | Bearer / Cookie | `analytics.read` | Vertical Assignment | `vertical_id` query | 401 / 403 |
| `/api/v1/analytics/administrative`| GET | Bearer / Cookie | `analytics.admin` | Admin / Sports Core | None | 401 / 403 |
| `/api/v1/admin/audit-logs` | GET | Bearer / Cookie | `audit.read` | Admin Role | Multi-filter params | 401 / 403 |
| `/api/v1/admin/config` | GET / POST | Bearer / Cookie | `config.read` / `config.update`| Admin Role | `SystemConfigCreate` | 401 / 403 |
| `/api/v1/health` | GET | None | Public Liveness | None | None | 200 |
| `/api/v1/health/database` | GET | None | Public Database Health | None | None | 200 / 503 |

---

## 5. Automated Backup & Disaster Recovery Architecture

- **Tooling**: `scripts/backup_postgres.py` and `scripts/restore_postgres.py`.
- **Archive Format**: Gzip-compressed timestamped SQL dumps (`.sql.gz`) with SHA-256 integrity checksums and `.meta.json` table catalogs.
- **Retention**: Automated rolling 7-day backup retention.
- **Verification**: `python scripts/restore_postgres.py --verify-only` validates archive uncompressed hash fidelity.
