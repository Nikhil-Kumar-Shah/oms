#!/usr/bin/env bash
# ==============================================================================
# PARADOX SPORTS OMS - BASH DEVELOPMENT LAUNCHER
# Starts backend and frontend concurrently for Linux/macOS
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

echo "===================================================================="
echo "PARADOX SPORTS OMS - DEVELOPMENT RUNTIME"
echo "===================================================================="

# Activate virtual environment if present
if [ -d "${ROOT_DIR}/.venv" ]; then
    source "${ROOT_DIR}/.venv/bin/activate"
fi

# Run pre-flight Python script
python3 "${ROOT_DIR}/scripts/start_dev.py"
