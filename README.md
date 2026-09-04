# Paradox Sports Operations Management System (OMS)

[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2015+-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016+-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![TailwindCSS](https://img.shields.io/badge/Styling-TailwindCSS%204-38B2AC?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

An authoritative, enterprise-grade Operations Management System engineered specifically for the **Paradox Sports Department**. The platform provides end-to-end governance, cross-vertical workforce orchestration, event lifecycle operations, compliance directives, dynamic form workflows, and immutable audit logging.

Built with a hardened Python/FastAPI backend, an optimized Next.js frontend, and an authoritative PostgreSQL data store, designed for on-premise virtual machines or cloud deployment (such as Azure Virtual Machines and Azure Database for PostgreSQL Flexible Server).

---

## Table of Contents

1. [System Architecture & Working Mechanism](#1-system-architecture--working-mechanism)
2. [Database Architecture & Complete Data Model](#2-database-architecture--complete-data-model)
3. [Prerequisites & System Requirements](#3-prerequisites--system-requirements)
4. [Environment Configuration](#4-environment-configuration)
5. [Local Development Setup](#5-local-development-setup)
6. [Production Deployment Guide (Virtual Machine / Linux)](#6-production-deployment-guide-virtual-machine--linux)
7. [Operational Commands & Server Verification](#7-operational-commands--server-verification)
8. [Role-Based Access Control (RBAC) & Governance](#8-role-based-access-control-rbac--governance)
9. [Testing & Quality Assurance](#9-testing--quality-assurance)
10. [Maintainer](#10-maintainer)

---

## 1. System Architecture & Working Mechanism

The Paradox Sports OMS is designed around a zero-trust, server-authoritative architecture where business logic, role validation, vertical isolation, and data integrity checks are enforced strictly on the backend.

### Architectural Diagram

```
                             [ End Users / Web Browsers ]
                                          │
                                    HTTPS :443 / TLS 1.3
                                          ▼
                               [ Nginx Reverse Proxy ]
                     ┌────────────────────┴────────────────────┐
                     │                                         │
               /api/ & /health                           /* (Web UI)
                     ▼                                         ▼
         [ FastAPI + Uvicorn Workers ]               [ Next.js Node Service ]
               (Port 8000)                                (Port 3000)
                     │
         SQLAlchemy 2.x Pool (TCP 5432)
                     │
                     ▼
       [ PostgreSQL Database Engine ]
   (Local PostgreSQL 15+ or Azure Flexible Server)
```

### Request Lifecycle & Working Principles

1. **Edge Security & Reverse Proxy (Nginx):**
   * Terminates TLS 1.3 encryption with modern cipher suites.
   * Enforces global rate limits and stricter brute-force rate limits on `/api/v1/auth/login`.
   * Routes `/api/v1/*` and `/health` requests to the FastAPI backend service (127.0.0.1:8000).
   * Routes all frontend application traffic to the Next.js production server (127.0.0.1:3000).

2. **Backend Application Layer (FastAPI):**
   * **Security Middleware Stack:** Injects mandatory security headers (`Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`).
   * **Correlation Tracking:** Attaches a unique `X-Request-ID` to every HTTP transaction for end-to-end tracing.
   * **Authentication & Session Lifecycle:** Implements Argon2id password hashing and cryptographic token generation. Sessions are stored in the PostgreSQL database with SHA-256 token digests. Both HttpOnly cookies (`oms_session`) and `Authorization: Bearer <token>` headers are supported.
   * **Authoritative RBAC:** Validates fine-grained permissions (`resource.action`) and vertical divisional scopes on every API route before executing service operations.

3. **Frontend Application Layer (Next.js & React):**
   * Server-side rendering (SSR) and statically optimized pages via Next.js App Router.
   * Emberspire design system providing an accessible, responsive dark aesthetic.
   * Centralized HTTP client managing automatic authentication, session hydration, and error normalization.

---

## 2. Database Architecture & Complete Data Model

PostgreSQL serves as the **single authoritative source of truth**. The system strictly adheres to an enterprise **Zero Hard-Deletion Policy**: normal user actions transition records through explicit lifecycle states (`ACTIVE`, `COMPLETED`, `ARCHIVED`, `CANCELLED`, `DISABLED`) rather than deleting rows.

### Core Entity Relationship Structure

```
  [ Organizations ] ──1:N──> [ Verticals ] ──1:N──> [ UserVerticals ]
                                                            │
                                                            │ N:1
                                                            ▼
  [ Roles ] ──1:N──> [ UserRoles ] <──N:1──────────────── [ Users ]
      │                                                     │
     1:N                                                   1:N
      ▼                                                     ▼
  [ RolePermissions ] ──N:1──> [ Permissions ]       [ UserSessions ]
                                                     [ UserProfiles ]
                                                     [ AuditLogs ]
```

### Detailed Domain Models

#### A. Identity, Accounts & Sessions
* **`users`**: Authoritative account entity storing `username` (unique handle), `email` (unique registered address), `full_name`, `password_hash` (Argon2id), `account_status` (`ACTIVE`, `PENDING_ACTIVATION`, `SUSPENDED`, `DISABLED`), and timestamps.
* **`user_sessions`**: Active authenticated sessions indexed by `token_hash` (SHA-256), client IP, user agent, expiration time, and last activity tracking.
* **`user_profiles`**: Extended personnel information, contact details, emergency contacts, and operational notes.
* **`event_team_profiles`**: Activation tracking for external Event Team users, storing assigned event reference and approving Point of Contact (POC).

#### B. Organization & Operational Verticals
* **`organizations`**: Root tenant record (`Paradox Sports Department`, code: `PARADOX_SPORTS`).
* **`verticals`**: Operational divisions within the sports department (e.g., Football Operations, Cricket Operations, Athletics & Track, Logistics & Equipment, Media & Communications). Tracks lifecycle state (`ACTIVE`, `ARCHIVED`).
* **`user_verticals`**: Association table mapping users to vertical scopes, designating `is_primary` vertical ownership.

#### C. Role-Based Access Control (RBAC) & Governance
* **`roles`**: Standard canonical roles (`ADMIN`, `SPORTS_CORE`, `DEPUTY_CORE`, `SUPER_COORDINATOR`, `COORDINATOR`, `VOLUNTEER`, `EVENT_TEAM`).
* **`permissions`**: Granular permissions in `resource.action` notation (e.g., `tasks.create`, `reports.review`, `users.disable`).
* **`role_permissions`**: Mapping table binding canonical permissions to roles.
* **`user_roles`**: Mapping table binding users to assigned roles.
* **`user_permission_overrides`**: Per-user explicit grants or revocations taking precedence over role permissions.
* **`audit_logs`**: Append-only audit record capturing timestamp, actor ID, action type, resource type, resource ID, IP address, correlation ID, and JSON context.
* **`system_configs`**: Type-safe system settings (e.g., `system_name`, `maintenance_mode`, `audit_retention_days`).

#### D. Operational Work & Reporting
* **`tasks`**: Master task register supporting parent-child subtasks, priority (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), status (`PENDING`, `IN_PROGRESS`, `UNDER_REVIEW`, `COMPLETED`, `BLOCKED`, `CANCELLED`), health flags, deadline tracking, assignee, and vertical assignment.
* **`task_history`**: Audit log of all state transitions and field mutations.
* **`task_comments`**: Collaboration threads on tasks.
* **`daily_work_reports`**: Daily progress logs submitted by volunteers and coordinators, reviewed by vertical leadership.
* **`weekly_reports`**: Consolidated weekly executive summaries.

#### E. Event Operations & Readiness
* **`events`**: Sporting events and tournaments tracking venue, event head, primary POC, vertical, and lifecycle state (`DRAFT`, `PUBLISHED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`).
* **`event_members`**: Roster of volunteers and coordinators assigned to an event.
* **`event_readiness_items`**: Checklists verifying operations (equipment, safety, venue readiness, logistics) prior to event launch.

#### F. Cross-Vertical Coordination & Meetings
* **`requirements`**: Cross-vertical assistance requests (e.g., Athletics requesting Logistics for field barriers), tracking requesting vs. target vertical, responsible POC, priority, and fulfillment status.
* **`requirement_messages`**: Communication messages within a requirement workflow.
* **`meetings`**: Scheduled briefings, debriefs, and syncs, tracking vertical, organizer, location, meeting link, and minutes.
* **`meeting_participants`**: Rsvp status tracking (`ACCEPTED`, `DECLINED`, `TENTATIVE`, `PENDING`).
* **`meeting_action_items`**: Action items generated from meetings, convertible directly into tasks.

#### G. Dynamic Forms & Workflows
* **`forms`**: Dynamic form definitions created by authorized leads.
* **`form_versions`**: Schema-versioned form definitions with structured JSON field layouts.
* **`form_distributions`**: Scoped distribution targets (entire organization, specific vertical, or role group).
* **`form_submissions`**: Completed submissions from assigned participants.
* **`form_responses`**: Form responses undergoing multi-stage review workflows.

#### H. Communication & Compliance
* **`announcements`**: Broadcast messages targeted by vertical, role, or organization-wide.
* **`directives`**: Compliance orders issued by leadership requiring mandatory user acknowledgment.
* **`directive_acknowledgements`**: Audit tracking of users who have read and acknowledged directives.
* **`notifications`**: In-app notifications with read/unread tracking.
* **`communication_logs`**: External and official communication registry.

---

## 3. Prerequisites & System Requirements

### Hardware Recommendations
| Resource | Minimum (Development) | Recommended (Production VM) |
| :--- | :--- | :--- |
| **CPU** | 2 Cores | 4 Cores |
| **RAM** | 4 GB | 8 GB or 16 GB |
| **Storage** | 20 GB SSD | 50+ GB SSD / NVMe |
| **Network** | Local loopback | Static IP / Domain with HTTPS |

### Software & Runtime Dependencies
* **Operating System:** Ubuntu 22.04 LTS or Ubuntu 24.04 LTS (recommended for production); Windows 11 or macOS supported for local development.
* **Python:** Version `3.11` or `3.12` with `pip` and `venv`.
* **Node.js:** Version `20.x LTS` or `22.x LTS` with `npm` (v10+).
* **Database Engine:** PostgreSQL `15+` (Local instance or Azure Database for PostgreSQL Flexible Server).
* **Web Server / Reverse Proxy:** Nginx `1.18+` with SSL module.
* **System Utilities:** `git`, `curl`, `openssl`, `libpq-dev`.

---

## 4. Environment Configuration

The application uses explicit environment variables validated via Pydantic Settings. Development defaults are strictly isolated from production settings.

### Backend Configuration Reference (`.env` / `/etc/paradox-oms/production.env`)

```ini
# Application Mode (Must be 'production' on deployment servers)
APP_ENV=production
APP_NAME="Paradox Sports OMS"
APP_VERSION="1.0.0"
DEBUG=false

# Server Bind Settings
HOST=127.0.0.1
PORT=8000

# Security Keys (Must be a 64-character hex string generated with: openssl rand -hex 32)
SECRET_KEY=generate_a_cryptographically_secure_random_key_for_production

# Domain & CORS Restrictions
ALLOWED_HOSTS="oms.yourdomain.org,127.0.0.1,localhost"
CORS_ORIGINS="https://oms.yourdomain.org"
ENABLE_SECURITY_HEADERS=true
ENFORCE_HTTPS=true

# Database Connection (Azure Database for PostgreSQL or Local)
# Format: postgresql+psycopg2://<user>:<password>@<host>:5432/<dbname>?sslmode=require
DATABASE_URL="postgresql+psycopg2://oms_admin:StrongPassword@your-pg.postgres.database.azure.com:5432/paradox_oms?sslmode=require"

# Connection Pool Settings
DATABASE_POOL_SIZE=15
DATABASE_MAX_OVERFLOW=25
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800

# Rate Limiting
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_GLOBAL_PER_MINUTE=120

# Session Cookie Security
SESSION_COOKIE_NAME="oms_session"
SESSION_EXPIRE_HOURS=24
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE="lax"

# Documentation Access Control
ENABLE_DOCS=false
API_DOCS_USERNAME="secure_docs_admin"
API_DOCS_PASSWORD="ComplexPasswordHere"
```

### Frontend Configuration Reference (`frontend/.env.local` / `/etc/paradox-oms/frontend.production.env`)

```ini
NODE_ENV=production
PORT=3000
HOSTNAME=127.0.0.1

NEXT_PUBLIC_APP_NAME="Paradox Sports OMS"
NEXT_PUBLIC_APP_ENV="production"

# API Base URL (Relative path through the reverse proxy)
NEXT_PUBLIC_API_BASE_URL="/api/v1"
```

---

## 5. Local Development Setup

### Option A: Windows (PowerShell)

1. **Clone Repository & Navigate:**
   ```powershell
   git clone <repository-url>
   cd "OMS @"
   ```

2. **Set Up Python Virtual Environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

3. **Install Frontend Dependencies:**
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

4. **Configure Local Environment:**
   Copy the example environment files:
   ```powershell
   Copy-Item .env.example .env
   Copy-Item frontend\.env.example frontend\.env.local
   ```
   *Edit `.env` to point to your local PostgreSQL server (`postgresql://postgres:password@127.0.0.1:5432/paradox_oms`).*

5. **Apply Database Migrations:**
   ```powershell
   alembic upgrade head
   ```

6. **Create Your Initial System Administrator Account:**
   ```powershell
   python scripts/create_production_admin.py
   ```

7. **Verify Server Readiness:**
   ```powershell
   python scripts/check_server.py
   ```

8. **Start the Development Servers:**
   ```powershell
   python scripts/start_dev.py
   ```
   * Access Web UI: **http://localhost:3000**
   * Backend API: **http://127.0.0.1:8000**
   * API Health Check: **http://127.0.0.1:8000/health**

---

### Option B: Linux / macOS

```bash
# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

# Set up frontend
cd frontend && npm install && cd ..

# Setup environment files
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# Run migrations and provision admin
alembic upgrade head
python scripts/create_production_admin.py

# Verify & run
python scripts/check_server.py
python scripts/start_dev.py
```

---

## 6. Production Deployment Guide (Virtual Machine / Linux)

### 🚀 One-Command Master Activation (Recommended)

On any clean **Ubuntu 22.04 LTS or 24.04 LTS Virtual Machine** (e.g. Azure Virtual Machine), you can deploy, configure, build, and activate the entire production server with a **single command**:

```bash
# 1. Clone repository to /opt/paradox-oms
sudo git clone <your-repo-url> /opt/paradox-oms
cd /opt/paradox-oms

# 2. Run the master production activator
sudo bash activate_production.sh
```

To configure with your production domain name:
```bash
sudo bash activate_production.sh --domain oms.yourdomain.org
```

**What `activate_production.sh` executes automatically:**
1. **Prerequisite Downloads:** Automatically updates packages and installs Python 3.11/3.12, Node.js 20 LTS, Nginx, PostgreSQL client (`libpq-dev`), `git`, `curl`, and `openssl`.
2. **Service Isolation:** Creates the dedicated `omsapp` system user and `/etc/paradox-oms` configuration space.
3. **Automated Secret Generation:** Generates production environment files (`production.env` and `frontend.production.env`) with a cryptographically secure `SECRET_KEY` (`openssl rand -hex 32`) and strict permissions (`chmod 600`).
4. **Backend Build:** Creates the Python virtual environment and installs all application dependencies (`pip install -e .`).
5. **Frontend Build:** Installs dependencies and compiles the Next.js optimized production bundle (`npm run build`).
6. **Database Migration:** Executes all Alembic migrations (`alembic upgrade head`) and verifies schema readiness.
7. **Process Management:** Installs, enables, and restarts systemd services (`paradox-backend.service` and `paradox-frontend.service`).
8. **Reverse Proxy & Firewall:** Deploys Nginx reverse proxy configuration and enables UFW firewall (Ports 22, 80, 443).
9. **Live Health Probe:** Verifies live HTTP responses on ports 8000, 3000, and Nginx port 80.

---

### Step-by-Step Manual Deployment Walkthrough

If you prefer to perform the deployment steps manually instead of using `activate_production.sh`:

#### Step 1: Provision VM & Install OS Packages

Connect to your Ubuntu server via SSH and install dependencies:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev \
    nodejs npm nginx git curl libpq-dev openssl certbot python3-certbot-nginx

# Ensure Node.js 20+ LTS is active (if distribution node is older)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### Step 2: Create Service User & Directory

```bash
# Create dedicated application system user
sudo useradd -r -s /bin/false -d /opt/paradox-oms omsapp

# Create application and configuration directories
sudo mkdir -p /opt/paradox-oms /etc/paradox-oms /var/log/paradox-oms
sudo chown -R omsapp:omsapp /opt/paradox-oms /var/log/paradox-oms
```

### Step 3: Deploy Repository Codebase

```bash
# Clone the repository into /opt/paradox-oms
sudo git clone <your-repo-url> /opt/paradox-oms
cd /opt/paradox-oms

# Set up Python virtual environment
sudo python3 -m venv .venv
sudo .venv/bin/pip install --upgrade pip
sudo .venv/bin/pip install -e .

# Install and build frontend production package
cd /opt/paradox-oms/frontend
sudo npm ci
sudo npm run build
cd /opt/paradox-oms
```

### Step 4: Configure Production Secrets

Create secure production environment files readable only by `omsapp`:

```bash
# Create production environment files
sudo cp /opt/paradox-oms/deployment/production.env.example /etc/paradox-oms/production.env
sudo cp /opt/paradox-oms/deployment/frontend.production.env.example /etc/paradox-oms/frontend.production.env

# Generate a 64-char random secret key
SECRET_HEX=$(openssl rand -hex 32)
echo "Generated SECRET_KEY: $SECRET_HEX"

# Edit configurations with your domain, Azure PostgreSQL credentials, and secret key
sudo nano /etc/paradox-oms/production.env
sudo nano /etc/paradox-oms/frontend.production.env

# Secure file permissions (Owner: omsapp, Permissions: 600)
sudo chown -R omsapp:omsapp /etc/paradox-oms
sudo chmod 600 /etc/paradox-oms/*.env
```

### Step 5: Initialize Database & Provision Administrator

```bash
# Run database schema migrations against Azure PostgreSQL
sudo -u omsapp /opt/paradox-oms/.venv/bin/alembic upgrade head

# Provision the primary System Administrator
sudo -u omsapp /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/create_production_admin.py

# Verify system readiness
sudo -u omsapp /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/check_server.py
```

### Step 6: Configure Systemd Services

Deploy systemd unit files to manage processes with automatic restarts:

```bash
# Copy unit files
sudo cp /opt/paradox-oms/deployment/paradox-backend.service /etc/systemd/system/
sudo cp /opt/paradox-oms/deployment/paradox-frontend.service /etc/systemd/system/
sudo cp /opt/paradox-oms/deployment/paradox-oms.target /etc/systemd/system/

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable paradox-backend.service paradox-frontend.service paradox-oms.target

# Start services
sudo systemctl start paradox-oms.target

# Verify status
sudo systemctl status paradox-backend.service
sudo systemctl status paradox-frontend.service
```

### Step 7: Configure Nginx Reverse Proxy & SSL

```bash
# Copy Nginx site configuration
sudo cp /opt/paradox-oms/deployment/paradox-oms.nginx.conf /etc/nginx/sites-available/paradox-oms

# Edit server_name to match your actual domain
sudo nano /etc/nginx/sites-available/paradox-oms

# Enable configuration
sudo ln -sf /etc/nginx/sites-available/paradox-oms /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx syntax and reload
sudo nginx -t
sudo systemctl reload nginx

# Issue Let's Encrypt SSL certificate
sudo certbot --nginx -d oms.yourdomain.org
```

---

## 7. Operational Commands & Server Verification

All administrative and operational scripts are maintained in the [`scripts/`](file:///d:/OMS%20@/scripts) directory.

### Quick Reference Table

| Purpose | Script | Command |
| :--- | :--- | :--- |
| **Master Production Activation (1-Click)** | `activate_production.sh` | `sudo bash activate_production.sh` |
| **Verify Server & Production Readiness** | `check_server.py` | `python scripts/check_server.py` |
| **Start Backend Server** | `run_dev.py` | `python scripts/run_dev.py` |
| **Start Full Stack (Backend + Frontend)** | `start_dev.py` | `python scripts/start_dev.py` |
| **Provision System Administrator** | `create_production_admin.py` | `python scripts/create_production_admin.py` |
| **Purge / Clean Test Data** | `clean_test_data.py` | `python scripts/clean_test_data.py` |
| **Automated Database Backup** | `backup_postgres.py` | `python scripts/backup_postgres.py` |
| **Database Restoration** | `restore_postgres.py` | `python scripts/restore_postgres.py <backup_file>` |
| **Seed Default FAQs** | `seed_faqs.py` | `python scripts/seed_faqs.py` |

### Detailed Command Examples

```bash
# 1. Run complete health check (checks DB connection, Alembic migration, RBAC, and HTTP)
python scripts/check_server.py

# 2. Check health against a running remote production server
python scripts/check_server.py --url https://oms.yourdomain.org

# 3. Create an administrator non-interactively
python scripts/create_production_admin.py \
  --username admin \
  --email admin@paradoxsports.org \
  --full-name "System Administrator" \
  --password "SecureAdminPassword@123"

# 4. Perform an encrypted/compressed database snapshot
python scripts/backup_postgres.py

# 5. Restore database snapshot
python scripts/restore_postgres.py backups/backup_paradox_oms_20260904_120000.sql.gz
```

---

## 8. Role-Based Access Control (RBAC) & Governance

The platform implements a hierarchical, 7-role access model. All operational authorization decisions are strictly enforced at the database and API service boundaries.

```
       [ Level 6: ADMIN ]                -> System Governance, Configuration, User Creation
               │
       [ Level 5: SPORTS_CORE ]          -> Organization-wide Operational Authority
               │
       [ Level 4: DEPUTY_CORE ]          -> Department-wide Operational Delegation
               │
       [ Level 3: SUPER_COORDINATOR ]    -> Multi-Vertical Coordination Leadership
               │
       [ Level 2: COORDINATOR ]          -> Vertical Operational Management
               │
       [ Level 1: VOLUNTEER ]            -> Field Execution, Task Updates, Daily Logs
               │
       [ Level 0: EVENT_TEAM ]           -> External Tournament & Match Operations
```

### Universal Audience & Assignment Selector Rules
The **Universal Selector** (`UniversalAudienceSelector.tsx`) handles targeting tasks, announcements, directives, forms, and event staff:
1. **Admin Exclusion:** The `ADMIN` role and all `ADMIN` user accounts are **strictly excluded** from selection across all audience pickers and operational assignment targets.
2. **Vertical Isolation:** Non-executive personnel can only select users and teams within their assigned vertical division.
3. **Audience Broadcast Controls:** Organization-wide announcements and directives can only be published by `ADMIN`, `SPORTS_CORE`, or `DEPUTY_CORE` users.

---

## 9. Testing & Quality Assurance

### Automated Backend Tests
Run the comprehensive Pytest suite:

```bash
# Run all unit and integration tests
pytest

# Run core security, database, and authentication tests
pytest tests/test_health.py tests/test_database.py tests/test_rbac.py tests/test_auth.py tests/test_backend_security_boundary.py
```

### Frontend Production Validation
Verify TypeScript types and build output:

```bash
cd frontend
npm run build
```

---

## 10. Maintainer

Developed, architected, and maintained by:

**Nikhil Kumar Shah**  
*Lead Architect & Senior Systems Engineer*  
Paradox Sports Department
