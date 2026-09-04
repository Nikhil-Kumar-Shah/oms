# Development Setup Guide — Paradox Sports OMS

## 1. Environment Setup

### Activate Virtual Environment
```powershell
.venv\Scripts\activate
```

### Install Dependencies
```powershell
pip install -e .[dev]
```

---

## 2. Environment Configuration

Copy the template `.env.example` to `.env`:
```powershell
cp .env.example .env
```

Ensure `DATABASE_URL` is set to a valid PostgreSQL instance.

---

## 3. Database Migrations

### Apply Migrations to PostgreSQL
```powershell
alembic upgrade head
```

### Check Current Migration Version
```powershell
alembic current
```

### Create a New Migration
```powershell
alembic revision --autogenerate -m "description_of_change"
```

### Downgrade / Rollback Migration
```powershell
alembic downgrade -1
# Or to base:
alembic downgrade base
```

---

## 4. Running the Application

### Start Development Server
```powershell
python scripts/run_dev.py
```
Or via uvicorn directly:
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 5. Verification & Testing

### Run Pytest Test Suite
```powershell
pytest -v
```

### Run Performance Baseline & Persistence Verification Script
```powershell
python scripts/verify_phase1.py
```
