# Paradox Sports OMS — Production Deployment Runbook
**Target Environment:** Microsoft Azure Virtual Machine (Ubuntu 22.04 / 24.04 LTS)  
**Database:** Dedicated PostgreSQL 15+ Instance  
**Web Server / Proxy:** Nginx Reverse Proxy with TLS 1.3 Termination  
**Application Server:** FastAPI running under Uvicorn ASGI Workers (Systemd managed)

---

## 1. Production Architecture Topology

```text
[ Internet Clients ]
        │ HTTPS (Port 443)
        ▼
[ Nginx Reverse Proxy ]
  ├── SSL/TLS Termination (Certbot / Let's Encrypt)
  ├── Rate Limiting (Zone: auth_limit, global_api_limit)
  ├── Static File Direct Caching (/static/ -> 30d)
  └── Gzip Compression
        │ HTTP (Port 8000 on Loopback 127.0.0.1)
        ▼
[ FastAPI + Uvicorn Workers ] (Systemd: paradox-oms.service)
  ├── SecurityHeaders & RequestCorrelation Middleware
  ├── Argon2id Session & Authentication Engine
  ├── Server-Authoritative RBAC & Vertical Scoping
  └── Transactional Service Layer
        │ SQLAlchemy 2.x Connection Pool (TCP 5432)
        ▼
[ PostgreSQL Database ] (paradox_oms)
  └── Authoritative Persistent Storage & Audit Log
```

---

## 2. Server Provisioning & OS Setup

### Step 1: Base Packages Installation
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-venv python3-pip python3-dev \
    postgresql postgresql-contrib libpq-dev nginx certbot python3-certbot-nginx \
    curl git ufw htop logrotate
```

### Step 2: Dedicated Application User
```bash
sudo useradd -m -s /bin/bash omsapp
sudo mkdir -p /opt/paradox-oms /etc/paradox-oms /var/log/paradox-oms
sudo chown -R omsapp:omsapp /opt/paradox-oms /var/log/paradox-oms
sudo chmod 750 /etc/paradox-oms
```

---

## 3. PostgreSQL Database Configuration

### Step 1: Create Production Database & User
```bash
sudo -u postgres psql
```
```sql
CREATE USER oms_prod_user WITH PASSWORD 'STRONG_RANDOMLY_GENERATED_PASSWORD';
CREATE DATABASE paradox_oms OWNER oms_prod_user;
GRANT ALL PRIVILEGES ON DATABASE paradox_oms TO oms_prod_user;
\c paradox_oms
GRANT ALL ON SCHEMA public TO oms_prod_user;
\q
```

### Step 2: Recommended PostgreSQL Tuning (`/etc/postgresql/15/main/postgresql.conf`)
For a 2 vCPU / 8 GB RAM Azure VM (e.g. Standard_B2ms / Standard_D2s_v5):
```ini
max_connections = 100
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 20MB
min_wal_size = 1GB
max_wal_size = 4GB
```
Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## 4. Production Environment Configuration (`/etc/paradox-oms/production.env`)

Create `/etc/paradox-oms/production.env` owned by `root:omsapp` with permissions `640`:
```ini
# Application Configuration
APP_ENV=production
APP_NAME="Paradox Sports OMS"
APP_VERSION="1.0.0"
DEBUG=false
LOG_LEVEL=INFO

# Networking & Host Binding
HOST=127.0.0.1
PORT=8000
ALLOWED_HOSTS="oms.paradoxsports.org,127.0.0.1"
CORS_ORIGINS="https://oms.paradoxsports.org"
ENABLE_SECURITY_HEADERS=true
ENFORCE_HTTPS=true

# Cryptographic Keys (Generated with `openssl rand -hex 32`)
SECRET_KEY=e83a992cb00a2948bc88ef492048995a9df0014a93fcd873919eef9047bca881

# PostgreSQL Connection Pool
DATABASE_URL=postgresql://oms_prod_user:STRONG_RANDOMLY_GENERATED_PASSWORD@127.0.0.1:5432/paradox_oms
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800

# Session & Cookie Security
SESSION_COOKIE_NAME=oms_session
SESSION_EXPIRE_HOURS=24
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax

# Rate Limiting Settings
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_GLOBAL_PER_MINUTE=120
```

---

## 5. Systemd Service Setup

Install the unit file:
```bash
sudo cp /opt/paradox-oms/deployment/paradox-oms.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable paradox-oms.service
sudo systemctl start paradox-oms.service
```

Verify service status:
```bash
sudo systemctl status paradox-oms.service
```

---

## 6. Nginx & SSL/TLS Configuration

### Step 1: Link Site Configuration
```bash
sudo cp /opt/paradox-oms/deployment/paradox-oms.nginx.conf /etc/nginx/sites-available/paradox-oms.conf
sudo ln -s /etc/nginx/sites-available/paradox-oms.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

### Step 2: Issue Let's Encrypt SSL Certificate
```bash
sudo certbot --nginx -d oms.paradoxsports.org
```

### Step 3: Test and Reload Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. Automated Backups & Disaster Recovery

### Step 1: Setup Automated Nightly Backup Cron Job
```bash
sudo crontab -u omsapp -e
```
Add the following line to execute automated database backup nightly at 02:00 UTC with 7-day rotation:
```cron
0 2 * * * /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/backup_postgres.py >> /var/log/paradox-oms/backup.log 2>&1
```

### Step 2: Disaster Recovery Procedure
1. List available backups:
   ```bash
   python scripts/restore_postgres.py --list
   ```
2. Verify checksum integrity of the target backup:
   ```bash
   python scripts/restore_postgres.py --verify-only --file backups/oms_backup_...sql.gz
   ```
3. Restore database from backup:
   ```bash
   python scripts/restore_postgres.py --file backups/oms_backup_...sql.gz
   ```

---

## 8. Deployment Updates

To deploy new code updates to the Azure VM:
```bash
sudo bash /opt/paradox-oms/scripts/deploy.sh
```
