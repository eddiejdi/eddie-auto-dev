#!/usr/bin/env bash
set -euo pipefail

# toggle_autonomous_mode.sh
# Usage: toggle_autonomous_mode.sh on|off [--apply] [env-file]
# Default env file: /etc/autonomous_remediator.env
# If --apply is passed, the script will attempt to reload systemd and restart
# the `autonomous_remediator.service` (requires sudo).

CMD=${1:-}
APPLY=0
FILE="${3:-/etc/autonomous_remediator.env}"

if [ "${2:-}" = "--apply" ]; then
  APPLY=1
  FILE="${3:-/etc/autonomous_remediator.env}"
fi

if [ -z "$CMD" ] || { [ "$CMD" != "on" ] && [ "$CMD" != "off" ]; }; then
  echo "Usage: $0 on|off [--apply] [env-file]"
  exit 2
fi

if [ ! -f "$FILE" ]; then
  echo "Env file not found: $FILE" >&2
  exit 3
fi

VAL=0
if [ "$CMD" = "on" ]; then VAL=1; fi

BACKUP="${FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp -- "$FILE" "$BACKUP"
echo "Backup created: $BACKUP"

if grep -q '^AUTONOMOUS_MODE=' "$FILE"; then
  sed -i "s/^AUTONOMOUS_MODE=.*/AUTONOMOUS_MODE=${VAL}/" "$FILE"
else
  echo "AUTONOMOUS_MODE=${VAL}" >> "$FILE"
fi

echo "Set AUTONOMOUS_MODE=${VAL} in $FILE"

if [ "$VAL" -eq 1 ]; then
  echo "WARNING: Autonomous mode enabled. The agent may perform real actions."
  echo "Confirm you have set FLY_API_TOKEN and any required secrets in the env file." 
fi

if [ "$APPLY" -eq 1 ]; then
  echo "Reloading systemd and restarting autonomous_remediator.service (requires sudo)"
  sudo systemctl daemon-reload
  sudo systemctl restart autonomous_remediator.service
  sudo journalctl -u autonomous_remediator.service -n 200 --no-pager
fi
