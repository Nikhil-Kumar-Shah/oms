# Paradox Sports OMS — Operational Scripts Directory

This directory contains the authoritative maintenance, deployment, and management scripts for the Paradox Sports Operations Management System (OMS).

All temporary development and test verification scripts have been removed.

---

## Quick Reference Index

| Purpose | Script | Command |
| :--- | :--- | :--- |
| **Check Server & Production Readiness** | `check_server.py` | `python scripts/check_server.py` |
| **Start Backend Server** | `run_dev.py` | `python scripts/run_dev.py` |
| **Start Full Stack (Backend + Frontend)** | `start_dev.py` | `python scripts/start_dev.py` |
| **Create System Administrator Account** | `create_production_admin.py` | `python scripts/create_production_admin.py` |
| **Clean / Purge Test Data** | `clean_test_data.py` | `python scripts/clean_test_data.py` |
| **Backup PostgreSQL Database** | `backup_postgres.py` | `python scripts/backup_postgres.py` |
| **Restore PostgreSQL Database** | `restore_postgres.py` | `python scripts/restore_postgres.py <backup_file>` |
| **Master Production Activation & Hosting** | `activate_production.sh` | `sudo bash activate_production.sh` |
| **Linux Dev Service Launcher** | `dev.sh` | `bash scripts/dev.sh` |

---

## Detailed Script Descriptions

### 1. Check Server (`check_server.py`)
**When to run:** Before deploying, after configuration updates, or whenever you want to verify if the server and database are healthy and ready for production.

**What it does:**
- Validates environment configuration (`APP_ENV`, `DEBUG=False` in production, `SECRET_KEY` complexity).
- Tests PostgreSQL database connectivity and measures query round-trip latency.
- Validates that database migrations are fully synchronized to the Alembic head revision.
- Verifies core entity integrity (active System Administrator accounts, vertical count, RBAC roles, and permissions).
- Probes live HTTP endpoints (`/health` and `/`) if the server is running.

**Commands:**
```bash
# Standard check using current environment settings
python scripts/check_server.py

# Check against a specific running server URL
python scripts/check_server.py --url https://oms.paradoxsports.org

# Run database/migration checks without probing HTTP service
python scripts/check_server.py --skip-http
```

---

### 2. Create System Administrator (`create_production_admin.py`)
**When to run:** To provision the initial or additional System Administrator account with full system governance and operational permissions.

**Commands:**
```bash
# Interactive mode (prompts for username, email, full name, masked password)
python scripts/create_production_admin.py

# Non-interactive / automation mode
python scripts/create_production_admin.py --username admin --email admin@paradoxsports.org --full-name "System Administrator" --password "YourStrongPassword@123"
```

---

### 3. Clean Test Data (`clean_test_data.py`)
**When to run:** When you want to purge development, dummy, or benchmark test records from the database while preserving all canonical system configurations, roles, permissions, and administrator accounts.

**Command:**
```bash
python scripts/clean_test_data.py
```

---

### 4. Backup PostgreSQL Database (`backup_postgres.py`)
**When to run:** Scheduled cron or manual snapshot before system updates. Creates a compressed `.sql.gz` dump with SHA-256 checksum and metadata.

**Command:**
```bash
python scripts/backup_postgres.py
```

---

### 5. Restore PostgreSQL Database (`restore_postgres.py`)
**When to run:** Disaster recovery or cloning a database state from a backup archive.

**Command:**
```bash
python scripts/restore_postgres.py backups/backup_paradox_oms_YYYYMMDD_HHMMSS.sql.gz
```

---

### 6. Start Servers (`run_dev.py` & `start_dev.py`)
- `python scripts/run_dev.py`: Starts only the FastAPI backend server using Uvicorn.
- `python scripts/start_dev.py`: Starts both FastAPI backend (port 8000) and Next.js frontend (port 3000) concurrently.
