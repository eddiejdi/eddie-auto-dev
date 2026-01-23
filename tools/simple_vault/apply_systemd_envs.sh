#!/usr/bin/env bash
# Create systemd drop-in files pointing services to the SIMPLE_VAULT_PASSPHRASE_FILE
# Usage (dry-run): ./apply_systemd_envs.sh --env-file /full/path/to/passphrase
# To actually apply, run with sudo and --apply

set -euo pipefail

ENVFILE="/etc/default/simple_vault"
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENVFILE="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

units=(open-webui.service btc-webui-api.service eddie-telegram-bot.service)

echo "Will write EnvironmentFile=$ENVFILE to the following units:"
for u in "${units[@]}"; do echo " - $u"; done

if [ "$APPLY" -eq 0 ]; then
  echo "Dry-run. Re-run with --apply (as root) to apply changes." ; exit 0
fi

if [ "$EUID" -ne 0 ]; then
  echo "Must run as root to apply changes." >&2; exit 2
fi

for u in "${units[@]}"; do
  dropdir="/etc/systemd/system/${u}.d"
  mkdir -p "$dropdir"
  cat > "$dropdir/override.conf" <<EOF
[Service]
EnvironmentFile=$ENVFILE
EOF
  echo "Wrote $dropdir/override.conf"
done

systemctl daemon-reload || true
echo "Applied. Run 'systemctl restart <unit>' for services you want restarted."
