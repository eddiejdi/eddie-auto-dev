#!/usr/bin/env bash
# Install an EnvironmentFile for a systemd unit by decrypting repo vault secrets
# Usage: sudo tools/systemd/install_env_for_unit.sh eddie-calendar.service

set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <unit-name>" >&2
  exit 2
fi
UNIT="$1"
ENVFILE="/etc/default/${UNIT%%.service}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
EXPORT_SCRIPT="$REPO_DIR/tools/simple_vault/export_env.sh"

if [[ ! -x "$EXPORT_SCRIPT" ]]; then
  echo "Missing export helper: $EXPORT_SCRIPT" >&2
  exit 1
fi

echo "Generating $ENVFILE from vault..."
sudo bash "$EXPORT_SCRIPT" > "$ENVFILE"
sudo chmod 600 "$ENVFILE"
echo "Reloading systemd and restarting $UNIT"
sudo systemctl daemon-reload
sudo systemctl restart "$UNIT"
echo "Done"
