#!/usr/bin/env bash
set -euo pipefail
# Deploy and encrypt telegram bots config to /etc/eddie/telegram_bots.json.enc
# Usage: sudo ./scripts/deploy_telegram_bots.sh [source_json] [password]

SRC="${1:-specialized_agents/telegram_bots.example.json}"
PASS="${2:-130913}"
DEST_DIR="/etc/eddie"
DEST="$DEST_DIR/telegram_bots.json.enc"

if [ ! -f "$SRC" ]; then
  echo "Source file not found: $SRC" >&2
  exit 2
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl not installed. Install it and re-run." >&2
  exit 3
fi

mkdir -p "$DEST_DIR"
openssl enc -aes-256-cbc -salt -in "$SRC" -out "$DEST" -pass pass:"$PASS"
chmod 640 "$DEST"
chown root:root "$DEST"

cat <<EOF
Encrypted file written: $DEST
To allow the Agents API to read it, set environment variable:
  TELEGRAM_BOTS_PASS=$PASS
for the service user (e.g. via systemd drop-in or /etc/default/ file).
EOF
