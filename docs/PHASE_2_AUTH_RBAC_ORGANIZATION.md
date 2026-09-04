# Phase 2: Authentication, RBAC & Organization Architecture

## 1. System Overview
Phase 2 establishes a server-authoritative identity, authentication, session management, Role-Based Access Control (RBAC), explicit permission overrides, organizational hierarchy, and append-only audit logging for **Paradox Sports OMS**.

The backend architecture strictly enforces:
```
Browser / Client
       ↓
    FastAPI
       ↓
 Authentication
       ↓
Authorization / RBAC
       ↓
   Validation
       ↓
 Business Logic
       ↓
 SQLAlchemy 2.x
       ↓
   PostgreSQL
```

---

## 2. Organization Terminology & Hierarchy
The organizational model is strictly defined as:
```
Organization
    ↓
 Vertical
    ↓
  User
```
- **Zero Department Concept**: No Department tables, columns, terminology, or APIs exist anywhere in the system.
- **Verticals**: Database-driven divisions (`Football Operations`, `Cricket Operations`, `Athletics & Track`, etc.) linked to the parent `Organization`.

---

## 3. User Identity & Lifecycle Management
- **Primary Key**: UUIDv4 (`UUID(as_uuid=True)`).
- **Unique Handle**: `username` (lowercase, alphanumeric).
- **Password Security**: Argon2id hashing per RFC 9106 standards (`argon2-cffi`).
- **Account States**:
  - `ACTIVE`: Normal operational authentication permitted.
  - `DISABLED`: Authentication denied, active sessions revoked immediately, records retained.
  - `SUSPENDED`: Authentication denied, active sessions revoked immediately.
  - `ARCHIVED`: Authentication denied, historical data preserved.
- **Zero Hard-Deletion Policy**: Normal administrative operations never hard-delete users from PostgreSQL.

---

## 4. Session Management & Cryptography
- **Session Model**: `user_sessions` table in PostgreSQL.
- **Token Hashing**: Client receives a cryptographically secure 256-bit URL-safe session token. The database stores only the **SHA-256 hash** of the token.
- **Session Attributes**: `id`, `user_id`, `session_token_hash`, `created_at`, `expires_at`, `last_seen_at`, `revoked_at`, `ip_address`, `user_agent`.
- **Security Controls**:
  - HttpOnly, SameSite cookies with configurable secure flags.
  - Invalidation on logout (`revoked_at`).
  - Invalidation on account disable/suspension/archive.
  - Revocation of other sessions upon password change or admin password reset.

---

## 5. RBAC & Effective Permissions
- **Canonical System Roles**:
  - `ADMIN`: Full access to all organizational resources and administrative functions.
  - `SPORTS_CORE`: Department leadership with operational management authority.
  - `DEPUTY_CORE`: Deputy executive with operational management authority.
  - `SUPER_COORDINATOR`: Multi-vertical operational coordinator.
  - `COORDINATOR`: Vertical and fixture coordinator.
  - `VOLUNTEER`: Operational volunteer member.
  - `EVENT_TEAM`: Designated event team member.
- **Granular Permission Registry**:
  - Action-based codes (`users.read`, `users.create`, `users.update`, `users.disable`, `roles.manage`, `verticals.create`, `verticals.update`, `verticals.assign`, `audit.read`, etc.).
- **Server-Authoritative Effective Permissions Formula**:
  $$\text{Effective Permissions} = (\text{Role Permissions} \cup \text{Explicit Grants}) \setminus \text{Explicit Revocations}$$
  *Note: Users with the `ADMIN` role automatically possess all system permissions.*

---

## 6. Organization & Verticals
- **Tables**: `organizations`, `verticals`, `user_verticals`.
- **Integrity Constraints**: Unique constraint on `(organization_id, name)` for verticals.
- **Assignment Validation**: Users can only be assigned to `ACTIVE` verticals belonging to a valid organization.
- **Scope Authorization**: `require_vertical_scope(vertical_id)` prevents unassigned users from operating across vertical boundaries unless they hold executive leadership roles (`ADMIN` / `SPORTS_CORE`).

---

## 7. Append-Only Audit Logging
- **Table**: `audit_logs`
- **Fields**: `id`, `timestamp`, `actor_id`, `action`, `resource_type`, `resource_id`, `outcome`, `correlation_id`, `ip_address`, `details` (JSONB).
- **Sanitization**: Passwords, tokens, and cryptographic secrets are stripped before persisting to audit logs.
- **Immutability Protection**: The service layer raises `ImmutableAuditException` on any update or delete attempts.

---

## 8. API Endpoints Summary

### Authentication (`/api/v1/auth`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Authenticate credentials and create session | Public |
| `POST` | `/api/v1/auth/logout` | Revoke current session and clear cookie | Authenticated |
| `GET` | `/api/v1/auth/me` | Current profile, roles, effective permissions, verticals | Authenticated |
| `POST` | `/api/v1/auth/change-password` | Change password with old password verification | Authenticated |

### Organization (`/api/v1/organization`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/organization` | Organization profile and active verticals | Authenticated |
| `GET` | `/api/v1/organization/verticals` | List active vertical divisions | Authenticated |
| `GET` | `/api/v1/organization/verticals/{id}` | Vertical division details | Authenticated |

### Administration (`/api/v1/admin`)
| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/admin/users` | List user accounts with filters | `users.read` |
| `POST` | `/api/v1/admin/users` | Create user with roles & verticals | `users.create` |
| `GET` | `/api/v1/admin/users/{id}` | User detail by UUID | `users.read` |
| `PATCH` | `/api/v1/admin/users/{id}` | Update user profile | `users.update` |
| `POST` | `/api/v1/admin/users/{id}/disable` | Disable user and revoke all sessions | `users.disable` |
| `POST` | `/api/v1/admin/users/{id}/enable` | Restore user account to active | `users.update` |
| `POST` | `/api/v1/admin/users/{id}/reset-password` | Admin reset password | `users.update` |
| `POST` | `/api/v1/admin/users/{id}/roles` | Assign canonical roles | `roles.manage` |
| `POST` | `/api/v1/admin/users/{id}/verticals` | Assign vertical scopes | `verticals.assign` |
| `POST` | `/api/v1/admin/users/{id}/permissions` | Set explicit permission overrides | `permissions.manage` |
| `POST` | `/api/v1/admin/organization/verticals` | Create vertical division | `verticals.create` |
| `PATCH` | `/api/v1/admin/organization/verticals/{id}` | Update vertical status/info | `verticals.update` |
| `GET` | `/api/v1/admin/roles` | List system roles & permissions | `roles.read` |
| `GET` | `/api/v1/admin/permissions` | List permission registry | `permissions.read` |
| `GET` | `/api/v1/admin/audit-logs` | List append-only audit trail | `audit.read` |

---

## 9. Verification & Testing Strategy
- **Full Phase 1 Regression**: All 13 tests passed without regression.
- **Phase 2 Security & Functional Tests**: 36 dedicated tests passed (Total: 49 tests).
- **Mandatory Attack Scenarios**: All 19 security attacks tested and defended successfully.
- **Persistence Verification**: Verified that users, sessions, roles, verticals, and audit logs persist across fresh client connections and match direct raw PostgreSQL queries.
