# Database Architecture — Paradox Sports OMS

## 1. Authoritative Engine
PostgreSQL is the single authoritative source of truth. All reads and writes must pass through SQLAlchemy 2.x mapped queries with explicit transaction boundaries.

## 2. Configuration & Connection Pooling
Configured via `app/core/config.py` and managed in `app/core/database.py`:

| Parameter | Environment Variable | Default | Purpose |
|---|---|---|---|
| Database URI | `DATABASE_URL` | *Required* | Authoritative PostgreSQL connection string |
| Pool Size | `DATABASE_POOL_SIZE` | `5` | Base number of persistent connections |
| Max Overflow | `DATABASE_MAX_OVERFLOW` | `10` | Maximum surge connections |
| Pool Timeout | `DATABASE_POOL_TIMEOUT` | `30s` | Checkout timeout before raising error |
| Pool Recycle | `DATABASE_POOL_RECYCLE` | `1800s` | Lifetime before connection is refreshed |
| Pool Pre-Ping | Hardcoded (`True`) | `True` | Tests liveness before checkout (`SELECT 1`) |

## 3. Session & Transaction Lifecycle
- **Dependency**: `app.core.database.get_db` yields a request-scoped `Session`.
- **Commit**: Handled explicitly within services (`service.create()`, `service.update()`).
- **Rollback**: Guaranteed by `get_db()` on unhandled exceptions and within services on failed blocks.
- **Cleanup**: `session.close()` is executed in the `finally` block of `get_db()`.

## 4. Base Model Standards (`app/models/base.py`)
- **Declarative Base**: `Base(DeclarativeBase)`
- **UUID Primary Key**: `UUIDPrimaryKeyMixin` sets default `uuid.uuid4`, indexed and non-nullable.
- **Timestamps**: `TimestampMixin` sets `created_at` and `updated_at` with `DateTime(timezone=True)` using `datetime.now(timezone.utc)`.

## 5. Migrations with Alembic
- Configuration in `alembic.ini` and `migrations/env.py`.
- Target metadata linked directly to `Base.metadata`.
- All schema alterations are captured as versioned migration scripts in `migrations/versions/`.
- Direct manual DDL execution outside migrations is strictly prohibited.
