#!/usr/bin/env bash
set -euo pipefail

# deploy_named_tunnel_via_ssh.sh
# Copies Cloudflare named tunnel credentials and config to a remote host and enables systemd.
# Usage: ./deploy_named_tunnel_via_ssh.sh --host ${HOMELAB_HOST} --user homelab --tunnel eddie-homelab 

HOST=""
USER=""
TUNNEL="eddie-homelab"
CREDS_FILE=""
CONFIG_FILE=""

usage(){
  echo "Usage: $0 --host <host> --user <user> --tunnel <tunnel-name> --creds <creds.json> --config <config.yml>" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --tunnel) TUNNEL="$2"; shift 2 ;;
    --creds) CREDS_FILE="$2"; shift 2 ;;
    --config) CONFIG_FILE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$CREDS_FILE" ] || [ -z "$CONFIG_FILE" ]; then
  usage
fi

REMOTE_DIR="/etc/cloudflared"

echo "Copying credentials and config to ${USER}@${HOST}..."
scp "$CREDS_FILE" "${USER}@${HOST}:/tmp/" 
scp "$CONFIG_FILE" "${USER}@${HOST}:/tmp/"

echo "Moving files into place and setting permissions..."
ssh "${USER}@${HOST}" sudo mkdir -p "$REMOTE_DIR"
ssh "${USER}@${HOST}" sudo mv "/tmp/$(basename "$CREDS_FILE")" "$REMOTE_DIR/"
ssh "${USER}@${HOST}" sudo mv "/tmp/$(basename "$CONFIG_FILE")" "$REMOTE_DIR/config.yml"
ssh "${USER}@${HOST}" sudo chown root:root "$REMOTE_DIR/$(basename "$CREDS_FILE")" "$REMOTE_DIR/config.yml"
ssh "${USER}@${HOST}" sudo chmod 640 "$REMOTE_DIR/$(basename "$CREDS_FILE")" "$REMOTE_DIR/config.yml"

echo "Installing systemd unit for named tunnel and starting service..."
scp ./cloudflared-named@.service "${USER}@${HOST}:/tmp/cloudflared-named@.service"
ssh "${USER}@${HOST}" sudo mv /tmp/cloudflared-named@.service /etc/systemd/system/cloudflared-named@.service
ssh "${USER}@${HOST}" sudo systemctl daemon-reload
ssh "${USER}@${HOST}" sudo systemctl enable --now cloudflared-named@${TUNNEL}.service

echo "Deployed named tunnel '${TUNNEL}' to ${HOST}. Check:"
echo "  ssh ${USER}@${HOST} 'sudo systemctl status cloudflared-named@${TUNNEL}.service'"

exit 0
