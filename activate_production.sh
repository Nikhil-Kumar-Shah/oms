#!/usr/bin/env bash
# ==============================================================================
# PARADOX SPORTS OPERATIONS MANAGEMENT SYSTEM (OMS)
# Master Production Activation & Hosting Script (Single Source of Truth)
# ==============================================================================
# Architecture: Next.js (Port 3000) + FastAPI (Port 8000) + PostgreSQL (Local / Azure) + Nginx (:80/:443)
# Target OS: Ubuntu 22.04 LTS / Ubuntu 24.04 LTS (Debian-compatible)
#
# Usage:
#   sudo bash activate_production.sh
#   sudo bash activate_production.sh --domain oms.yourdomain.org
#   sudo bash activate_production.sh --skip-deps
# ==============================================================================

set -euo pipefail

# Text formatting
BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
CYAN="\033[96m"
RESET="\033[0m"

# Application directory and user paths
APP_USER="omsapp"
TARGET_DIR="/opt/paradox-oms"
CONFIG_DIR="/etc/paradox-oms"
LOG_DIR="/var/log/paradox-oms"
SCRIPT_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOMAIN="localhost"
SKIP_DEPS=false

# Parse optional arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --skip-deps)
      SKIP_DEPS=true
      shift
      ;;
    -h|--help)
      echo "Usage: sudo bash activate_production.sh [--domain your-domain.com] [--skip-deps]"
      exit 0
      ;;
    *)
      echo "Unknown parameter: $1"
      exit 1
      ;;
  esac
done

echo -e "\n${CYAN}${BOLD}==============================================================================${RESET}"
echo -e "${CYAN}${BOLD}   PARADOX SPORTS OMS — ONE-CLICK PRODUCTION SERVER ACTIVATOR                 ${RESET}"
echo -e "${CYAN}${BOLD}==============================================================================${RESET}"
echo -e "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo -e "Target Domain: ${BOLD}${DOMAIN}${RESET}\n"

# ------------------------------------------------------------------------------
# STEP 1: Sudo / Root Privilege Verification
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/10] Verifying Root Privileges...${RESET}"
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] ERROR: This script must be run as root.${RESET}" >&2
  echo -e "    Please run: ${BOLD}sudo bash activate_production.sh${RESET}" >&2
  exit 1
fi
echo -e "  ${GREEN}[✓]${RESET} Operating with root privileges."

# ------------------------------------------------------------------------------
# STEP 2: System Package & Dependency Installation
# ------------------------------------------------------------------------------
if [ "$SKIP_DEPS" = false ]; then
  echo -e "\n${BOLD}[2/10] Installing System Prerequisites & Runtimes...${RESET}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y

  # Essential system libraries, compilers, Nginx, UFW, PostgreSQL client
  apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    ufw \
    nginx \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    openssl \
    certbot \
    python3-certbot-nginx \
    logrotate \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev

  # Install Node.js 20 LTS if missing or outdated
  NEED_NODE=true
  if command -v node &> /dev/null; then
    NODE_MAJOR=$(node -v | cut -d'.' -f1 | tr -d 'v')
    if [ "$NODE_MAJOR" -ge 20 ]; then
      NEED_NODE=false
      echo -e "  ${GREEN}[✓]${RESET} Node.js $(node -v) is already installed."
    fi
  fi

  if [ "$NEED_NODE" = true ]; then
    echo -e "  [*] Installing Node.js 20.x LTS from NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    echo -e "  ${GREEN}[✓]${RESET} Node.js $(node -v) & npm $(npm -v) installed."
  fi
else
  echo -e "\n${BOLD}[2/10] Skipping system packages (--skip-deps active)...${RESET}"
fi

# ------------------------------------------------------------------------------
# STEP 3: Create Service User & Target Directories
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[3/10] Configuring Application Service User & Directory Structure...${RESET}"

if ! id -u "$APP_USER" &>/dev/null; then
  echo -e "  [*] Creating system user: ${APP_USER}..."
  useradd -r -s /bin/bash -d "$TARGET_DIR" "$APP_USER"
fi

mkdir -p "$TARGET_DIR" "$CONFIG_DIR" "$LOG_DIR" /var/www/certbot
chown -R "$APP_USER:$APP_USER" "$TARGET_DIR" "$CONFIG_DIR" "$LOG_DIR" /var/www/certbot
chmod 755 "$TARGET_DIR"
chmod 750 "$LOG_DIR"
chmod 755 "$CONFIG_DIR"

# Allow git operations in this repository across users
git config --system --add safe.directory "$TARGET_DIR" 2>/dev/null || git config --global --add safe.directory "$TARGET_DIR" 2>/dev/null || true

# Synchronize current repository to /opt/paradox-oms if running from outside
if [ "$SCRIPT_SOURCE_DIR" != "$TARGET_DIR" ]; then
  echo -e "  [*] Synchronizing repository to ${TARGET_DIR}..."
  rsync -a --exclude='.venv' --exclude='node_modules' --exclude='.next' --exclude='.git' \
    "$SCRIPT_SOURCE_DIR/" "$TARGET_DIR/"
  chown -R "$APP_USER:$APP_USER" "$TARGET_DIR"
fi
echo -e "  ${GREEN}[✓]${RESET} Application directory ready at ${TARGET_DIR}."

# ------------------------------------------------------------------------------
# STEP 4: Production Configuration & Secrets Validation
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[4/10] Validating Environment Configurations & Cryptographic Secrets...${RESET}"

# A. Backend Environment (/etc/paradox-oms/production.env)
if [ ! -f "${CONFIG_DIR}/production.env" ]; then
  echo -e "  [*] Generating production backend environment template..."
  NEW_SECRET=$(openssl rand -hex 32)
  
  # Check if there is an existing DATABASE_URL in .env to inherit
  INHERITED_DB_URL=""
  if [ -f "${TARGET_DIR}/.env" ]; then
    INHERITED_DB_URL=$(grep -E '^DATABASE_URL=' "${TARGET_DIR}/.env" | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
  fi

  if [ -z "$INHERITED_DB_URL" ]; then
    # Default to local PostgreSQL template
    INHERITED_DB_URL="postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/paradox_oms"
  fi

  cat > "${CONFIG_DIR}/production.env" <<EOF
# Paradox Sports OMS Production Environment
APP_ENV=production
APP_NAME="Paradox Sports OMS"
APP_VERSION="1.0.0"
DEBUG=false

HOST=127.0.0.1
PORT=8000

SECRET_KEY=${NEW_SECRET}

ALLOWED_HOSTS="${DOMAIN},127.0.0.1,localhost"
CORS_ORIGINS="https://${DOMAIN},http://${DOMAIN}"
ENABLE_SECURITY_HEADERS=true
ENFORCE_HTTPS=false

DATABASE_URL="${INHERITED_DB_URL}"
DATABASE_POOL_SIZE=15
DATABASE_MAX_OVERFLOW=25
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800

LOG_LEVEL=INFO
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_GLOBAL_PER_MINUTE=120

SESSION_COOKIE_NAME="oms_session"
SESSION_EXPIRE_HOURS=24
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE="lax"

ENABLE_DOCS=false
API_DOCS_USERNAME="admin_docs"
API_DOCS_PASSWORD="$(openssl rand -hex 12)"
EOF

  chown "$APP_USER:$APP_USER" "${CONFIG_DIR}/production.env"
  chmod 600 "${CONFIG_DIR}/production.env"
  echo -e "  ${GREEN}[✓]${RESET} Created ${CONFIG_DIR}/production.env with generated SECRET_KEY."
else
  echo -e "  ${GREEN}[✓]${RESET} Found existing ${CONFIG_DIR}/production.env."
fi

# B. Frontend Environment (/etc/paradox-oms/frontend.production.env)
if [ ! -f "${CONFIG_DIR}/frontend.production.env" ]; then
  cat > "${CONFIG_DIR}/frontend.production.env" <<EOF
NODE_ENV=production
PORT=3000
HOSTNAME=127.0.0.1
NEXT_PUBLIC_APP_NAME="Paradox Sports OMS"
NEXT_PUBLIC_APP_ENV="production"
NEXT_PUBLIC_API_BASE_URL="/api/v1"
EOF
  chown "$APP_USER:$APP_USER" "${CONFIG_DIR}/frontend.production.env"
  chmod 644 "${CONFIG_DIR}/frontend.production.env"
  echo -e "  ${GREEN}[✓]${RESET} Created ${CONFIG_DIR}/frontend.production.env."
else
  echo -e "  ${GREEN}[✓]${RESET} Found existing ${CONFIG_DIR}/frontend.production.env."
fi

# Ensure correct permissions on configuration directory and files
chown -R "$APP_USER:$APP_USER" "$CONFIG_DIR"
chmod 755 "$CONFIG_DIR"
chmod 600 "${CONFIG_DIR}/production.env" 2>/dev/null || true
chmod 644 "${CONFIG_DIR}/frontend.production.env" 2>/dev/null || true

# Copy configuration files directly to avoid symlink cross-directory access restrictions
rm -f "${TARGET_DIR}/.env" "${TARGET_DIR}/frontend/.env.local" "${TARGET_DIR}/frontend/.env.production.local"
cp "${CONFIG_DIR}/production.env" "${TARGET_DIR}/.env"
cp "${CONFIG_DIR}/frontend.production.env" "${TARGET_DIR}/frontend/.env.local"
cp "${CONFIG_DIR}/frontend.production.env" "${TARGET_DIR}/frontend/.env.production.local"

chown "$APP_USER:$APP_USER" "${TARGET_DIR}/.env" "${TARGET_DIR}/frontend/.env.local" "${TARGET_DIR}/frontend/.env.production.local"
chmod 600 "${TARGET_DIR}/.env"
chmod 644 "${TARGET_DIR}/frontend/.env.local" "${TARGET_DIR}/frontend/.env.production.local"

# ------------------------------------------------------------------------------
# STEP 5: Python Backend Virtual Environment & Package Installation
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[5/10] Building Python Backend Environment...${RESET}"
cd "$TARGET_DIR"

if [ ! -d "${TARGET_DIR}/.venv" ]; then
  echo -e "  [*] Creating Python virtual environment at ${TARGET_DIR}/.venv..."
  sudo -u "$APP_USER" python3 -m venv "${TARGET_DIR}/.venv"
fi

sudo -u "$APP_USER" "${TARGET_DIR}/.venv/bin/pip" install --upgrade pip setuptools wheel
sudo -u "$APP_USER" "${TARGET_DIR}/.venv/bin/pip" install -e "${TARGET_DIR}"
echo -e "  ${GREEN}[✓]${RESET} Python backend packages installed."

# ------------------------------------------------------------------------------
# STEP 6: Next.js Frontend Production Build
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[6/10] Compiling Next.js Production Frontend Bundle...${RESET}"
cd "${TARGET_DIR}/frontend"

sudo -u "$APP_USER" npm install --prefer-offline --no-audit --no-fund
sudo -u "$APP_USER" NEXT_TELEMETRY_DISABLED=1 npm run build
echo -e "  ${GREEN}[✓]${RESET} Next.js production build completed."
cd "$TARGET_DIR"

# ------------------------------------------------------------------------------
# STEP 7: Database Migration & Schema Verification
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[7/10] Executing PostgreSQL Database Migrations (Alembic)...${RESET}"
cd "$TARGET_DIR"

# Export variables for Alembic execution
set -a
source "${CONFIG_DIR}/production.env"
set +a

sudo -u "$APP_USER" -E "${TARGET_DIR}/.venv/bin/alembic" upgrade head
echo -e "  ${GREEN}[✓]${RESET} Alembic migrations successfully applied to latest head."

# Run automated readiness check
echo -e "  [*] Running readiness check utility..."
sudo -u "$APP_USER" -E "${TARGET_DIR}/.venv/bin/python" "${TARGET_DIR}/scripts/check_server.py" --skip-http

# ------------------------------------------------------------------------------
# STEP 8: Systemd Services Deployment & Activation
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[8/10] Installing & Activating Systemd Production Services...${RESET}"

# Copy service unit files
cp "${TARGET_DIR}/deployment/paradox-backend.service" /etc/systemd/system/
cp "${TARGET_DIR}/deployment/paradox-frontend.service" /etc/systemd/system/
cp "${TARGET_DIR}/deployment/paradox-oms.target" /etc/systemd/system/

systemctl daemon-reload
systemctl enable paradox-backend.service paradox-frontend.service paradox-oms.target
systemctl restart paradox-backend.service
systemctl restart paradox-frontend.service
echo -e "  ${GREEN}[✓]${RESET} Systemd services (backend + frontend) started and enabled on boot."

# ------------------------------------------------------------------------------
# STEP 9: Nginx Reverse Proxy Configuration & Firewall
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[9/10] Configuring Nginx Reverse Proxy & Firewall...${RESET}"

# Generate standalone Nginx config compatible with HTTP (and ready for HTTPS via Certbot)
NGINX_CONF="/etc/nginx/sites-available/paradox-oms.conf"
cat > "$NGINX_CONF" <<EOF
# Paradox Sports OMS — Nginx Production Reverse Proxy
upstream paradox_backend {
    server 127.0.0.1:8000 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

upstream paradox_frontend {
    server 127.0.0.1:3000 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} localhost _;

    client_max_body_size 25M;

    # ACME Challenge for Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
    }

    # API Routing -> FastAPI Backend
    location /api/ {
        proxy_pass http://paradox_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    # Health Check Endpoint
    location /health {
        proxy_pass http://paradox_backend/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    # Web Application -> Next.js Frontend
    location / {
        proxy_pass http://paradox_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/paradox-oms.conf
rm -f /etc/nginx/sites-enabled/default

# Test Nginx syntax and reload
nginx -t
systemctl reload nginx
echo -e "  ${GREEN}[✓]${RESET} Nginx reverse proxy configured and active."

# Configure UFW Firewall
if command -v ufw &> /dev/null; then
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow 22/tcp comment 'SSH'
  ufw allow 80/tcp comment 'HTTP'
  ufw allow 443/tcp comment 'HTTPS'
  ufw --force enable
  echo -e "  ${GREEN}[✓]${RESET} UFW firewall enabled (Ports 22, 80, 443 open; internal ports protected)."
fi

# ------------------------------------------------------------------------------
# STEP 10: Live End-to-End Health Verification
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[10/10] Performing Live End-to-End Verification...${RESET}"
sleep 3

BACKEND_UP=false
FRONTEND_UP=false

for i in {1..15}; do
  if curl -sf http://127.0.0.1:8000/health &>/dev/null; then
    BACKEND_UP=true
    break
  fi
  sleep 1
done

for i in {1..15}; do
  if curl -sf http://127.0.0.1:3000 &>/dev/null; then
    FRONTEND_UP=true
    break
  fi
  sleep 1
done

PUBLIC_IP=$(curl -s -m 3 ifconfig.me || hostname -I | awk '{print $1}')

echo -e "\n${GREEN}${BOLD}==============================================================================${RESET}"
echo -e "${GREEN}${BOLD}       PARADOX SPORTS OMS IS ACTIVATED & RUNNING IN PRODUCTION!              ${RESET}"
echo -e "${GREEN}${BOLD}==============================================================================${RESET}"
echo -e "  • ${BOLD}Web Portal URL:${RESET}         http://${DOMAIN} (or http://${PUBLIC_IP})"
echo -e "  • ${BOLD}Backend Health Probe:${RESET}   http://${DOMAIN}/health"
echo -e "  • ${BOLD}Backend Status:${RESET}         $([ "$BACKEND_UP" = true ] && echo -e "${GREEN}ACTIVE (Port 8000)${RESET}" || echo -e "${RED}WAITING${RESET}")"
echo -e "  • ${BOLD}Frontend Status:${RESET}        $([ "$FRONTEND_UP" = true ] && echo -e "${GREEN}ACTIVE (Port 3000)${RESET}" || echo -e "${RED}WAITING${RESET}")"
echo -e "  • ${BOLD}Reverse Proxy:${RESET}          ${GREEN}ACTIVE (Nginx Port 80)${RESET}"
echo -e "  • ${BOLD}Service User:${RESET}           ${APP_USER}"
echo -e "  • ${BOLD}Configuration:${RESET}          ${CONFIG_DIR}/production.env"
echo -e "=============================================================================="

# Check if admin user is present
set +e
ADMIN_COUNT=$(sudo -u "$APP_USER" -E "${TARGET_DIR}/.venv/bin/python" -c "
from app.core.database import SessionLocal
from app.models.user import User
from app.models.rbac import UserRole, Role
with SessionLocal() as db:
    cnt = db.query(User).join(UserRole).join(Role).filter(Role.name == 'ADMIN', User.account_status == 'ACTIVE').count()
    print(cnt)
" 2>/dev/null || echo "0")
set -e

if [ "$ADMIN_COUNT" -eq 0 ]; then
  echo -e "\n${YELLOW}${BOLD}[!] NOTICE: No System Administrator account exists in the database.${RESET}"
  echo -e "    Run the following command to provision your administrator account:"
  echo -e "    ${BOLD}sudo -u omsapp /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/create_production_admin.py${RESET}\n"
else
  echo -e "\n  ${GREEN}[✓]${RESET} System Administrator account is provisioned and active."
fi

echo -e "${CYAN}${BOLD}Useful Operational Commands:${RESET}"
echo -e "  • Check Server Readiness:    ${BOLD}sudo -u omsapp /opt/paradox-oms/.venv/bin/python /opt/paradox-oms/scripts/check_server.py${RESET}"
echo -e "  • View Backend Logs:         ${BOLD}journalctl -u paradox-backend.service -f${RESET}"
echo -e "  • View Frontend Logs:        ${BOLD}journalctl -u paradox-frontend.service -f${RESET}"
echo -e "  • Restart Application:       ${BOLD}sudo systemctl restart paradox-oms.target${RESET}"
if [ "$DOMAIN" != "localhost" ] && [ "$DOMAIN" != "127.0.0.1" ]; then
  echo -e "  • Enable Free SSL (HTTPS):   ${BOLD}sudo certbot --nginx -d ${DOMAIN}${RESET}"
fi
echo -e "==============================================================================\n"
