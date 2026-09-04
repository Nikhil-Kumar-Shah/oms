# Production Deployment & Operations Guide
**Paradox Sports Operations Management System (OMS)**

---

## 1. Executive Summary

This guide details the end-to-end production deployment, configuration, process lifecycle, monitoring, backup, and recovery procedures for the Paradox Sports Operations Management System (OMS) on Ubuntu 22.04 / 24.04 LTS (e.g. Azure Linux Virtual Machine).

---

## 2. Infrastructure Requirements & Architecture

- **Operating System**: Ubuntu 22.04 LTS or Ubuntu 24.04 LTS.
- **Compute**: Minimum 2 vCPU, 4 GB RAM, 30 GB SSD.
- **Components**:
  - Python 3.12 (`python3.12-venv`)
  - Node.js 20 LTS & npm
  - PostgreSQL 14+ (Local service or Azure Database for PostgreSQL)
  - Nginx 1.18+ (Reverse proxy & TLS termination)
  - Certbot (Let's Encrypt automated TLS certificate manager)
  - Systemd (Process supervision & boot recovery)

---

## 3. Fresh Ubuntu VM Provisioning

Run the automated provisioning script as `root`:

```bash
sudo bash /opt/paradox-oms/deployment/setup_ubuntu_vm.sh
```

### What this script configures:
1. Installs Python 3.12, Node.js 20 LTS, PostgreSQL 16, Nginx, UFW, Fail2ban, and Certbot.
2. Configures dedicated unprivileged system user `omsapp:omsapp`.
3. Creates directories `/opt/paradox-oms`, `/etc/paradox-oms`, `/var/log/paradox-oms`.
4. Generates hardened `/etc/paradox-oms/production.env` and `/etc/paradox-oms/frontend.production.env` with `0600` permissions.
5. Configures UFW firewall (allows ports 22, 80, 443; strictly blocks ports 3000, 8000, 5432 from public access).
6. Installs and registers Systemd service units (`paradox-backend.service`, `paradox-frontend.service`, `paradox-oms.target`).

---

## 4. Production TLS / SSL Certificate Setup

Obtain an SSL certificate for your configured domain using Certbot:

```bash
sudo certbot --nginx -d oms.paradoxsports.org
```

Certbot will automatically provision and install certificates to `/etc/letsencrypt/live/oms.paradoxsports.org/`.

---

## 5. Automated Idempotent Deployment (`deploy.sh`)

Deploy or update the application with a single command:

```bash
sudo -u omsapp /opt/paradox-oms/deployment/deploy.sh
```

### Deployment Workflow:
```
Git pull / Code Sync
       ↓
Python 3.12 venv sync & dependency installation
       ↓
Alembic PostgreSQL Database Migrations (alembic upgrade head)
       ↓
Next.js Production Build (npm ci && npm run build)
       ↓
Systemd Service Restart (paradox-backend & paradox-frontend)
       ↓
Nginx Configuration Validation & Reload (nginx -t && systemctl reload nginx)
       ↓
Automated Health Verification Probes (Port 8000 & Port 3000)
       ↓
Deployment Complete
```

## 6. Creating Initial Production Administrator Account

In production, you should **never** run `seed_dev.py` (which creates mock development data). Instead, run the secure interactive admin provisioning tool:

```bash
sudo -u omsapp /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/create_production_admin.py
```

### Interactive Prompts:
1. **Username**: (3–50 alphanumeric characters or underscores)
2. **Email Address**: (Official administrator email)
3. **Full Name**: (Administrator full display name)
4. **Secure Password**: (Masked password input with confirmation; enforces minimum 10 characters, uppercase, lowercase, digit, and special symbol)

### Security Features:
- **Anti-Hijacking / Collision Check**: If the username or email already exists in the database, the script **immediately aborts** with an alert and prevents accidental overwrite.
- **Argon2id Cryptographic Hashing**: Password is never stored in plain text.
- **RBAC Role Assignment**: Grants the full `ADMIN` role with all operational and governance privileges.
- **PostgreSQL Audit Trail**: Generates an immutable `ADMIN_ACCOUNT_PROVISIONED` audit entry.

---

## 7. Service Management & Operations

### 6.1 Check Stack Status
```bash
# Check master target status
sudo systemctl status paradox-oms.target

# Check individual services
sudo systemctl status paradox-backend.service
sudo systemctl status paradox-frontend.service
sudo systemctl status nginx
sudo systemctl status postgresql
```

### 6.2 Restart Stack
```bash
# Restart entire application stack
sudo systemctl restart paradox-backend paradox-frontend

# Reload Nginx
sudo nginx -t && sudo systemctl reload nginx
```

### 6.3 Process Logs & Diagnostics
```bash
# Live backend logs (FastAPI / Uvicorn)
sudo journalctl -u paradox-backend.service -f

# Live frontend logs (Next.js)
sudo journalctl -u paradox-frontend.service -f

# Nginx access and error logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

---

## 7. Failure Recovery & Reboot Resilience

### 7.1 Boot Recovery
Both `paradox-backend.service` and `paradox-frontend.service` are enabled in `multi-user.target`:
- Upon VM reboot, Systemd automatically starts PostgreSQL $\rightarrow$ FastAPI $\rightarrow$ Next.js $\rightarrow$ Nginx in exact dependency order.
- The public URL (`https://oms.paradoxsports.org`) remains unchanged.

### 7.2 Service Crash Resilience
- If the Python or Node.js process crashes, Systemd automatically restarts the service within 5 seconds (`Restart=always`, `RestartSec=5s`).

---

## 8. Backup & Disaster Recovery

### 8.1 Automated PostgreSQL Database Backup
Create a daily cron job `/etc/cron.daily/paradox-oms-backup`:
```bash
#!/usr/bin/env bash
BACKUP_DIR="/var/backups/paradox-oms"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

sudo -u postgres pg_dump paradox_oms_prod | gzip > "${BACKUP_DIR}/oms_db_${TIMESTAMP}.sql.gz"

# Retain backups for 30 days
find "${BACKUP_DIR}" -name "oms_db_*.sql.gz" -mtime +30 -delete
```

### 8.2 Database Restore Procedure
```bash
# 1. Stop application services
sudo systemctl stop paradox-backend.service paradox-frontend.service

# 2. Restore database
gunzip -c /var/backups/paradox-oms/oms_db_YYYYMMDD_HHMMSS.sql.gz | sudo -u postgres psql paradox_oms_prod

# 3. Restart application services
sudo systemctl start paradox-backend.service paradox-frontend.service
```

---

## 9. Rollback Procedure

If a deployment fails validation:

```bash
# 1. Checkout previous stable Git commit
cd /opt/paradox-oms
git checkout <previous-commit-hash>

# 2. Re-run deployment script
sudo -u omsapp /opt/paradox-oms/deployment/deploy.sh
```
