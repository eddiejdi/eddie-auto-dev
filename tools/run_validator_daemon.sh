#!/usr/bin/env bash
# Simple daemon runner for tools/auto_validate_redirect.py
# Writes logs to /tmp/auto_validate_daemon.log. Safe to run as non-root.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
SCRIPT="$ROOT_DIR/tools/auto_validate_redirect.py"
LOG="/tmp/auto_validate_daemon.log"

cd "$ROOT_DIR"
echo "[run_validator_daemon] starting at $(date -Is)" >> "$LOG"
while true; do
  echo "[run_validator_daemon] launching validator at $(date -Is)" >> "$LOG"
  # run the validator; allow Python to run unbuffered output
  /usr/bin/env python3 -u "$SCRIPT" >> "$LOG" 2>&1 || echo "[run_validator_daemon] validator exited with $? at $(date -Is)" >> "$LOG"
  sleep 5
done
