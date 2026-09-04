#!/usr/bin/env bash
# Forwarding launcher to the root master production activator
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT_DIR}/activate_production.sh" "$@"
