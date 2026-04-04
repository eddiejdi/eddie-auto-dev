#!/usr/bin/env bash
# Gera dump e export LTFS rotativo (para agendamento cron/systemd timer).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR" && pwd)"

python3 "$ROOT_DIR/ltfs_recovery.py" --backup-catalog
