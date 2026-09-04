# Development Runtime & Local Environment Guide
**Paradox Sports Operations Management System (OMS)**

---

## 1. Prerequisites

Ensure the following tools are installed on your development machine:
- **Python 3.12+**: Python runtime with `pip` and `venv`.
- **Node.js 20+ LTS & npm**: Node.js JavaScript runtime.
- **PostgreSQL 14+**: Local or containerized PostgreSQL instance.

---

## 2. Environment Setup

### 2.1 Backend Environment (`.env`)
Copy the development environment template:
```bash
cp deployment/development.env.example .env
```
Ensure your `DATABASE_URL` in `.env` matches your local PostgreSQL credentials:
```env
DATABASE_URL="postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/paradox_oms_dev"
```

### 2.2 Frontend Environment (`frontend/.env.local`)
Copy the frontend development environment template:
```bash
cp deployment/frontend.development.env.example frontend/.env.local
```

---

## 3. One-Command Development Launcher

Start both FastAPI backend (Port 8000) and Next.js frontend (Port 3000) concurrently with database pre-flight checks and hot reload:

### On Windows / PowerShell:
```powershell
python scripts/start_dev.py
```

### On Linux / macOS / Bash:
```bash
./scripts/dev.sh
```

---

## 4. Manual / Multi-Terminal Startup Procedure

If you prefer running services in separate terminal windows:

### Terminal 1: Database Migrations & FastAPI Backend
```bash
# 1. Activate Virtual Environment
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# 2. Run Alembic Database Migrations
alembic upgrade head

# 3. Start FastAPI Server with Hot Reload
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2: Next.js Frontend Development Server
```bash
cd frontend

# 1. Install Dependencies
npm install

# 2. Start Next.js Development Server
npm run dev -- -p 3000
```

---

## 5. Development URLs & Ports

| Service | URL | Notes |
|---|---|---|
| **Frontend Application** | `http://localhost:3000` | Next.js Turbo dev server with HMR |
| **Backend REST API** | `http://127.0.0.1:8000/api/v1` | FastAPI endpoints |
| **API Health Probe** | `http://127.0.0.1:8000/health` | Minimal public health probe |
| **Interactive API Docs** | `http://127.0.0.1:8000/docs` | Swagger UI (User: `admin` / Pass: `password`) |
| **PostgreSQL Database** | `127.0.0.1:5432` | Local PostgreSQL instance |

---

## 6. Running Tests & Quality Checks

### Run Backend Pytest Suite
```bash
pytest tests/ -v
```

### Run Frontend Static Checks
```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

### Run Full E2E & Production Acceptance Suite
```bash
python scripts/verify_phase6_production_acceptance.py
python scripts/verify_phase7_runtime.py
```
