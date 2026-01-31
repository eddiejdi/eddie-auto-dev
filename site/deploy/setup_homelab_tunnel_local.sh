#!/usr/bin/env bash
set -euo pipefail

# setup_homelab_tunnel_local.sh
# Usage: sudo ./setup_homelab_tunnel_local.sh <PUBLIC_USER>@<PUBLIC_HOST> [PUBLIC_SSH_PORT]
# Run this on the homelab (192.168.15.2) as a user able to sudo and access Open WebUI (localhost:3000).

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <PUBLIC_USER>@<PUBLIC_HOST> [PUBLIC_SSH_PORT]"
  exit 2
fi

REMOTE=$1
SSH_PORT=${2:-22}
SERVICE_PATH=/etc/systemd/system/openwebui-ssh-tunnel.service

echo "[1/6] Ensuring SSH key exists for homelab user..."
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
  echo "Generating ed25519 SSH key (no passphrase)..."
  ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -N "" -C "openwebui-tunnel"
else
  echo "SSH key already exists: $HOME/.ssh/id_ed25519"
fi

echo "[2/6] Copying public key to remote ($REMOTE)..."
ssh-copy-id -p "$SSH_PORT" -i "$HOME/.ssh/id_ed25519.pub" "$REMOTE" || true

cat > /tmp/openwebui-ssh-tunnel.service <<EOF
[Unit]
Description=Reverse SSH tunnel for OpenWebUI (homelab -> public server)
After=network-online.target
Wants=network-online.target

[Service]
User=$(whoami)
Restart=always
RestartSec=10
ExecStart=/usr/bin/ssh -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes -N -R 127.0.0.1:13300:127.0.0.1:3000 -p ${SSH_PORT} ${REMOTE}

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/openwebui-ssh-tunnel.service $SERVICE_PATH
sudo chown root:root $SERVICE_PATH
sudo chmod 644 $SERVICE_PATH

echo "[3/6] Reloading systemd and enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable --now openwebui-ssh-tunnel

sleep 1

echo "[4/6] Checking service status..."
if sudo systemctl is-active --quiet openwebui-ssh-tunnel; then
  echo "Service started successfully"
else
  echo "Service failed to start - check 'sudo journalctl -u openwebui-ssh-tunnel -n 50'"
fi

echo "[5/6] Verifying remote side (via SSH) that remote port 13300 is listening on public host (127.0.0.1:13300)..."
ssh -p "$SSH_PORT" "${REMOTE#*@}" 'ss -ltnp 2>/dev/null | grep 13300 || true' || echo "Could not check remote listening ports (permission or firewall issues)."

echo "[6/6] Done. On the public server, configure Nginx to proxy to http://127.0.0.1:13300/ (see site/deploy/openwebui-nginx.conf)."

echo "Tips:"
echo " - Ensure the public server's SSH user allows port forwarding."
echo " - If using a firewall on the public server, no open port is required (Nginx talks to local 13300)."
