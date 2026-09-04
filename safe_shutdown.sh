#!/usr/bin/env bash
# ==============================================================================
# PARADOX SPORTS OMS - ROOT SAFE SHUTDOWN LAUNCHER
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/scripts/safe_shutdown.sh" "$@"
