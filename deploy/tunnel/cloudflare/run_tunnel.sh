#!/usr/bin/env bash
set -euo pipefail

# Script de ajuda para instalar e rodar cloudflared rapidamente (modo demo)
# Uso: sudo ./run_tunnel.sh <TUNNEL_NAME> <HOSTNAME> <LOCAL_SERVICE>

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <TUNNEL_NAME> <HOSTNAME> <LOCAL_SERVICE>"
  echo "Example: $0 my-eddie-tunnel eddie.example.com http://localhost:8501"
  exit 1
fi

TUNNEL_NAME="$1"
HOSTNAME="$2"
LOCAL_SERVICE="$3"

echo "Installing cloudflared (deb)..."
curl -L -o /tmp/cloudflared.deb \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
sudo dpkg -i /tmp/cloudflared.deb

echo "Logging in to Cloudflare (interactive)"
cloudflared tunnel login

echo "Creating tunnel: $TUNNEL_NAME"
TUNNEL_ID=$(cloudflared tunnel create "$TUNNEL_NAME" | awk '/Created tunnel/ {print $3; exit}') || true
echo "Tunnel created: $TUNNEL_ID"

echo "Writing config to /etc/cloudflared/config.yml"
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json
ingress:
  - hostname: $HOSTNAME
    service: $LOCAL_SERVICE
  - service: http_status:404
metrics: 127.0.0.1:8081
EOF

echo "Installing systemd unit..."
sudo tee /etc/systemd/system/cloudflared-tunnel.service > /dev/null <<'UNIT'
[Unit]
Description=cloudflared Tunnel (auto)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel run --config /etc/cloudflared/config.yml --name ${TUNNEL_NAME}
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-tunnel.service

echo "Tunnel should be running. Check: sudo journalctl -u cloudflared-tunnel -f"
