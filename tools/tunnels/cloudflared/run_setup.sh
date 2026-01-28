#!/usr/bin/env bash
set -euo pipefail

echo "This script helps to setup cloudflared tunnel (interactive)."
echo "Run on the homelab host as a user with home dir and sudo access."

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Please install first."
  exit 1
fi

read -p "Tunnel name (example: homelab-tunnel): " TUNNEL_NAME
cloudflared tunnel create "$TUNNEL_NAME"

TUNNEL_ID=$(cloudflared tunnel list | awk -v name="$TUNNEL_NAME" '$2==name {print $1}')
echo "Created tunnel id: $TUNNEL_ID"

echo "Now run: cloudflared tunnel route dns $TUNNEL_ID homelab.rpa4all.com"
echo "And create /etc/cloudflared/config.yml using config.yml.example as base."
echo "Then enable the systemd service: sudo cp tools/tunnels/cloudflared/cloudflared.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now cloudflared@${TUNNEL_NAME}.service"
