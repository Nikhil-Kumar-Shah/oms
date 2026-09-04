#!/usr/bin/env bash
# ==============================================================================
# PARADOX SPORTS OPERATIONS MANAGEMENT SYSTEM (OMS)
# Production Activation & Management Script (active_production.sh)
# ==============================================================================
# Single primary entry point forwarding to activate_production.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/activate_production.sh" "$@"
