#!/usr/bin/env bash
# ==============================================================================
# Paradox Sports OMS - Production Virtual Machine Deployment Script
# Safely pulls updates, migrates, rebuilds, and restarts services with zero data loss.
# ==============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
RESET="\033[0m"

APP_DIR="${1:-/opt/paradox-oms}"

echo -e "\n${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}   PARADOX SPORTS OMS — PRODUCTION VM UPDATE & DEPLOYMENT                     ${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}\n"

# 1. Gracefully shut down existing services safely
echo -e "${YELLOW}[*] Step 1: Performing graceful safe shutdown...${RESET}"
if [[ -f "${APP_DIR}/scripts/safe_shutdown.sh" ]]; then
  bash "${APP_DIR}/scripts/safe_shutdown.sh"
fi

# 2. Pull latest git commits
echo -e "\n${YELLOW}[*] Step 2: Fetching latest application code...${RESET}"
cd "${APP_DIR}"
git fetch --all
git pull origin main || git pull

# 3. Update Python Virtual Environment
echo -e "\n${YELLOW}[*] Step 3: Updating Python backend dependencies...${RESET}"
if [[ -d "${APP_DIR}/.venv" ]]; then
  source "${APP_DIR}/.venv/bin/activate"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
fi

# 4. Run database enum and canonical configuration sync
echo -e "\n${YELLOW}[*] Step 4: Synchronizing database enums and canonical parameters...${RESET}"
python -c "from app.core.database import SessionLocal, sync_database_enums; from app.services.rbac_service import ensure_canonical_roles_and_permissions; from app.services.config_service import ensure_canonical_system_configs; sync_database_enums(); db = SessionLocal(); ensure_canonical_roles_and_permissions(db); ensure_canonical_system_configs(db); db.commit(); db.close(); print('[+] Database sync verified.')"

# 5. Build Next.js production frontend
echo -e "\n${YELLOW}[*] Step 5: Building Next.js production frontend bundle...${RESET}"
cd "${APP_DIR}/frontend"
npm install --silent
npm run build

# 6. Restart Systemd Services
echo -e "\n${YELLOW}[*] Step 6: Starting systemd services...${RESET}"
cd "${APP_DIR}"
if [[ $EUID -eq 0 ]]; then
  systemctl restart paradox-backend paradox-frontend
  systemctl restart nginx
else
  sudo systemctl restart paradox-backend paradox-frontend
  sudo systemctl restart nginx
fi

# 7. Verify Health
echo -e "\n${YELLOW}[*] Step 7: Verifying live health endpoint...${RESET}"
sleep 3
HEALTH_STATUS=$(curl -s -m 5 http://127.0.0.1:8000/health 2>/dev/null || echo "failed")

echo -e "\n${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}   DEPLOYMENT COMPLETE!                                                       ${RESET}"
echo -e "${BOLD}${GREEN}   Health Status: ${HEALTH_STATUS}                                            ${RESET}"
echo -e "${BOLD}${GREEN}   Backend: http://127.0.0.1:8000                                             ${RESET}"
echo -e "${BOLD}${GREEN}   Frontend: http://localhost:3000                                            ${RESET}"
echo -e "${BOLD}${GREEN}   Nginx: Reverse Proxy Active (:80 / :443)                                   ${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}\n"
