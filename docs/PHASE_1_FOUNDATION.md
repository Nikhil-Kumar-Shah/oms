# Phase 1: Foundation Architecture Report

## 1. System Objective & Boundaries
Phase 1 establishes the clean backend foundation for Paradox Sports Operations Management System (OMS).
The backend enforces PostgreSQL as the single authoritative database with no intermediate caches pretending to be persistence, and without client-side data assumptions.

## 2. Core Stack
- **Framework**: FastAPI (async HTTP server with OpenAPI generation)
- **Database Driver & ORM**: PostgreSQL via `psycopg2-binary` & SQLAlchemy 2.x
- **Schema & Settings Validation**: Pydantic v2 & `pydantic-settings`
- **Migrations**: Alembic with automated revision tracking
- **Verification UI**: Server-rendered Jinja2 templates (`/dev`)
- **Testing**: Pytest with HTTPX TestClient

## 3. Organizational Terminology
The organizational hierarchy is strictly defined as:
```
Organization
    ↓
 Vertical
    ↓
  User
```
There is **no Department concept** in this codebase. Verticals represent the organizational divisions throughout the system.

## 4. Database Persistence Model
- **Connection Pooling**: SQLAlchemy `QueuePool` with configurable `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT`, and `DATABASE_POOL_RECYCLE`.
- **Fail-Fast Policy**: If PostgreSQL is unreachable, the system fails explicitly and logs clear connection errors. No fallback to SQLite is allowed.
- **Base Model Conventions**:
  - Primary Keys: UUIDv4 (`UUID(as_uuid=True)`)
  - Timestamps: Timezone-aware UTC `created_at` and `updated_at` (`DateTime(timezone=True)`)
  - Indexing: Explicit naming convention for constraints (`pk_*`, `fk_*`, `ix_*`, `uq_*`, `ck_*`).

## 5. SystemTestRecord Verification Entity
A single temporary foundation verification model `SystemTestRecord` is established to verify:
1. `POST /api/v1/test-records`: Creation and transaction commit (`BEGIN -> INSERT -> COMMIT`).
2. `GET /api/v1/test-records`: Query execution and retrieval.
3. `GET /api/v1/test-records/{id}`: Single-entity lookup by UUID.
4. Error handling and transaction rollback (`BEGIN -> INSERT -> ERROR -> ROLLBACK`).

## 6. Correlation ID & Observability
Every incoming HTTP request receives or generates an `X-Request-ID` header.
Structured log output formats:
`[Timestamp] [LogLevel] [req_id:UUID] [module:lineno]: Message`
Response headers include `X-Request-ID` and `X-Process-Time-Ms`.
