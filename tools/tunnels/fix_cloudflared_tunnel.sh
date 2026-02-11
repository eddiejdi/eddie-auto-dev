#!/usr/bin/env bash
set -euo pipefail

# fix_cloudflared_tunnel.sh
# Wrapper that deploys credentials/config (via deploy_named_tunnel_via_ssh.sh)
# and ensures cloudflared is installed and the named systemd service is enabled
# Usage: ./fix_cloudflared_tunnel.sh --host <host> --user <user> --tunnel <name> [--creds-secret <item>] [--config-secret <item>] [--creds <file>] [--config <file>]

usage(){
  cat <<EOF >&2
Usage: $0 --host <host> --user <user> --tunnel <name> [--creds-secret <item>] [--config-secret <item>] [--creds <file>] [--config <file>]

This script will:
  - call tools/tunnels/deploy_named_tunnel_via_ssh.sh to copy credentials/config and install the systemd unit
  - ensure /usr/local/bin/cloudflared exists on the remote and install it if missing
  - create /var/lib/cloudflared and set permissions
  - reload systemd and restart the named service

EOF
  exit 2
}

HOST=""
USER=""
TUNNEL=""
CREDS_SECRET=""
CONFIG_SECRET=""
CREDS_FILE=""
CONFIG_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --tunnel) TUNNEL="$2"; shift 2 ;;
    --creds-secret) CREDS_SECRET="$2"; shift 2 ;;
    --config-secret) CONFIG_SECRET="$2"; shift 2 ;;
    --creds) CREDS_FILE="$2"; shift 2 ;;
    --config) CONFIG_FILE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$TUNNEL" ]; then
  usage
fi

# Build arguments for deploy script: let it handle secrets/files
DEPLOY_ARGS=(--host "$HOST" --user "$USER" --tunnel "$TUNNEL")
if [ -n "$CREDS_FILE" ]; then
  DEPLOY_ARGS+=(--creds "$CREDS_FILE")
elif [ -n "$CREDS_SECRET" ]; then
  DEPLOY_ARGS+=(--creds-secret "$CREDS_SECRET")
fi
if [ -n "$CONFIG_FILE" ]; then
  DEPLOY_ARGS+=(--config "$CONFIG_FILE")
elif [ -n "$CONFIG_SECRET" ]; then
  DEPLOY_ARGS+=(--config-secret "$CONFIG_SECRET")
fi

echo "[fix] Deploying creds/config and systemd unit to ${USER}@${HOST} (tunnel=${TUNNEL})"
./tools/tunnels/deploy_named_tunnel_via_ssh.sh "${DEPLOY_ARGS[@]}"

echo "[fix] Ensuring cloudflared installed on remote host..."
ssh "${USER}@${HOST}" bash -s <<'REMOTE'
set -euo pipefail
ARCH=$(uname -m)
case "$ARCH" in
  x86_64|amd64) FILE_NAME=cloudflared-linux-amd64 ;; 
  aarch64|arm64) FILE_NAME=cloudflared-linux-arm64 ;; 
  *) FILE_NAME=cloudflared-linux-amd64 ;;
esac
if command -v cloudflared &> /dev/null; then
  echo "cloudflared already present: $(command -v cloudflared)"
else
  echo "Downloading cloudflared for $ARCH"
  URL="https://github.com/cloudflare/cloudflared/releases/latest/download/${FILE_NAME}"
  TMP=/tmp/cloudflared
  curl -fsSL -o "$TMP" "$URL"
  sudo install -m 0755 "$TMP" /usr/local/bin/cloudflared
  rm -f "$TMP"
  echo "Installed /usr/local/bin/cloudflared"
fi

echo "Ensuring /var/lib/cloudflared exists"
sudo mkdir -p /var/lib/cloudflared
sudo chown root:root /var/lib/cloudflared

echo "Reloading systemd and restarting named service"
sudo systemctl daemon-reload || true
sudo systemctl enable --now cloudflared-named@${TUNNEL}.service || true
sudo systemctl restart cloudflared-named@${TUNNEL}.service || true

echo "Service status:"
sudo systemctl status cloudflared-named@${TUNNEL}.service --no-pager
echo "Recent logs:"
sudo journalctl -u cloudflared-named@${TUNNEL}.service --no-pager -n 50 || true
REMOTE

echo "[fix] Done. Verifique o status remoto para confirmar." 

exit 0
