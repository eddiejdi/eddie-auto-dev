#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
DROPIN_DIR="$SYSTEMD_DIR/specialized-agents-api.service.d"
DROPIN_FILE="$DROPIN_DIR/secrets.conf"

SECRETS_AGENT_URL="${SECRETS_AGENT_URL:-http://192.168.15.2:8088}"
SECRETS_AGENT_API_KEY="${SECRETS_AGENT_API_KEY:-}"
CONUBE_SECRET_NAME="${CONUBE_SECRET_NAME:-conube/rpa4all}"

if [[ -z "$SECRETS_AGENT_API_KEY" ]]; then
  echo "SECRETS_AGENT_API_KEY nao definido." >&2
  echo "Exemplo:" >&2
  echo "  SECRETS_AGENT_API_KEY=... $0" >&2
  exit 1
fi

sudo mkdir -p "$DROPIN_DIR"
sudo tee "$DROPIN_FILE" >/dev/null <<EOF
[Service]
Environment="SECRETS_AGENT_URL=$SECRETS_AGENT_URL"
Environment="SECRETS_AGENT_API_KEY=$SECRETS_AGENT_API_KEY"
Environment="CONUBE_SECRET_NAME=$CONUBE_SECRET_NAME"
EOF

sudo chmod 600 "$DROPIN_FILE"
sudo systemctl daemon-reload
sudo systemctl restart specialized-agents-api.service

echo "Drop-in instalado em $DROPIN_FILE"
echo "specialized-agents-api.service reiniciado"
