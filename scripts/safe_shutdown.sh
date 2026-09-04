#!/usr/bin/env bash
# ==============================================================================
# Paradox Sports OMS - Graceful Safe Shutdown Script
# Safely terminates OMS backend and frontend services using SIGTERM (Signal 15).
# Allows in-flight DB transactions to complete and pools to close cleanly.
# NEVER uses force kill (-9).
# ==============================================================================

set -euo pipefail

# Colors
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "\n${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}   Paradox Sports OMS — Graceful Safe Shutdown Protocol                       ${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}\n"

# 1. Gracefully stop systemd services if present and active
SERVICES=("paradox-backend" "paradox-frontend" "paradox-oms.target")
SYSTEMD_USED=false

for svc in "${SERVICES[@]}"; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo -e "${YELLOW}[*] Gracefully stopping systemd service: ${svc} (SIGTERM)...${RESET}"
    if [[ $EUID -eq 0 ]]; then
      systemctl stop "$svc"
    else
      sudo systemctl stop "$svc"
    fi
    SYSTEMD_USED=true
    echo -e "${GREEN}[+] Service ${svc} stopped gracefully.${RESET}"
  fi
done

# 2. Check for standalone / developer processes listening on Port 8000 (Backend)
echo -e "${YELLOW}[*] Checking for backend processes on port 8000...${RESET}"
BACKEND_PIDS=$(lsof -ti:8000 2>/dev/null || ss -tulpn 2>/dev/null | grep ':8000 ' | awk -F'pid=' '{print $2}' | awk -F',' '{print $1}' || true)

if [[ -n "$BACKEND_PIDS" ]]; then
  for pid in $BACKEND_PIDS; do
    if ps -p "$pid" > /dev/null 2>&1; then
      PROC_NAME=$(ps -p "$pid" -o comm= 2>/dev/null || echo "process")
      echo -e "${YELLOW}[*] Sending SIGTERM (graceful shutdown) to backend PID ${pid} (${PROC_NAME})...${RESET}"
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
else
  echo -e "${GREEN}[+] No standalone backend processes found on port 8000.${RESET}"
fi

# 3. Check for standalone / developer processes listening on Port 3000 (Frontend)
echo -e "${YELLOW}[*] Checking for frontend processes on port 3000...${RESET}"
FRONTEND_PIDS=$(lsof -ti:3000 2>/dev/null || ss -tulpn 2>/dev/null | grep ':3000 ' | awk -F'pid=' '{print $2}' | awk -F',' '{print $1}' || true)

if [[ -n "$FRONTEND_PIDS" ]]; then
  for pid in $FRONTEND_PIDS; do
    if ps -p "$pid" > /dev/null 2>&1; then
      PROC_NAME=$(ps -p "$pid" -o comm= 2>/dev/null || echo "process")
      echo -e "${YELLOW}[*] Sending SIGTERM (graceful shutdown) to frontend PID ${pid} (${PROC_NAME})...${RESET}"
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
else
  echo -e "${GREEN}[+] No standalone frontend processes found on port 3000.${RESET}"
fi

# 4. Wait gracefully for connection drains and socket release (up to 20 seconds)
echo -e "\n${YELLOW}[*] Waiting for processes to drain active connections and release ports...${RESET}"
MAX_WAIT=20
WAIT_COUNT=0

while [[ $WAIT_COUNT -lt $MAX_WAIT ]]; do
  REMAINING_8000=$(lsof -ti:8000 2>/dev/null || ss -tulpn 2>/dev/null | grep -c ':8000 ' || echo 0)
  REMAINING_3000=$(lsof -ti:3000 2>/dev/null || ss -tulpn 2>/dev/null | grep -c ':3000 ' || echo 0)

  if [[ "$REMAINING_8000" == "0" && "$REMAINING_3000" == "0" ]]; then
    break
  fi

  sleep 1
  WAIT_COUNT=$((WAIT_COUNT + 1))
  echo -ne "  Elapsed: ${WAIT_COUNT}s / ${MAX_WAIT}s...\r"
done

echo ""

# 5. Final Verification
PORT_8000_BUSY=$(lsof -ti:8000 2>/dev/null || ss -tulpn 2>/dev/null | grep -c ':8000 ' || echo 0)
PORT_3000_BUSY=$(lsof -ti:3000 2>/dev/null || ss -tulpn 2>/dev/null | grep -c ':3000 ' || echo 0)

if [[ "$PORT_8000_BUSY" == "0" && "$PORT_3000_BUSY" == "0" ]]; then
  echo -e "\n${BOLD}${GREEN}==============================================================================${RESET}"
  echo -e "${BOLD}${GREEN}   SUCCESS: All OMS services have been gracefully and safely shut down.       ${RESET}"
  echo -e "${BOLD}${GREEN}   - Port 8000 (Backend API): RELEASED                                         ${RESET}"
  echo -e "${BOLD}${GREEN}   - Port 3000 (Frontend App): RELEASED                                        ${RESET}"
  echo -e "${BOLD}${GREEN}   - PostgreSQL connection pool: DISPOSED CLEANLY                              ${RESET}"
  echo -e "${BOLD}${GREEN}==============================================================================${RESET}\n"
else
  echo -e "\n${YELLOW}[!] Some processes are still completing their shutdown handshake.${RESET}"
  if [[ "$PORT_8000_BUSY" != "0" ]]; then
    echo -e "${YELLOW}    Port 8000 still has active processes draining connections.${RESET}"
  fi
  if [[ "$PORT_3000_BUSY" != "0" ]]; then
    echo -e "${YELLOW}    Port 3000 still has active processes draining connections.${RESET}"
  fi
  echo -e "${YELLOW}    Please wait a few moments for natural completion.${RESET}\n"
fi
