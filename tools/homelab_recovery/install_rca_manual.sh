#!/bin/bash
# Manual installation of RCA services on homelab runner
# Executes the same steps as the deploy-to-homelab.yml workflow

set -euo pipefail

HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"

echo "=== Installing RCA services on homelab ==="

ssh "$HOMELAB_USER@$HOMELAB_HOST" << 'REMOTE_SCRIPT'
set -euo pipefail

echo "Step 1: Fetching latest code from repo..."
cd ~/eddie-auto-dev
git fetch origin main
git checkout main
git pull origin main

echo "Step 2: Creating RCA directories..."
mkdir -p ~/eddie-auto-dev/tools/homelab_recovery

echo "Step 3: Copying RCA scripts..."
cp -r tools/homelab_recovery/* ~/eddie-auto-dev/tools/homelab_recovery/ || true
cp -f tools/agent_api_client.py ~/eddie-auto-dev/tools/ || true

echo "Step 4: Creating systemd user directory..."
mkdir -p ~/.config/systemd/user

echo "Step 5: Creating agent-api.service..."
cat > ~/.config/systemd/user/agent-api.service <<'SERVICE'
[Unit]
Description=Agent RCA API (user)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 %h/eddie-auto-dev/tools/homelab_recovery/simple_agent_api.py
Restart=on-failure
RestartSec=3
StandardOutput=append:/tmp/agent-api.service.log
StandardError=append:/tmp/agent-api.service.err

[Install]
WantedBy=default.target
SERVICE

echo "Step 6: Creating agent-consumer.service..."
cat > ~/.config/systemd/user/agent-consumer.service <<'SERVICE'
[Unit]
Description=Agent RCA Consumer Loop (user)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 %h/eddie-auto-dev/tools/homelab_recovery/agent_consumer_loop.py
Restart=on-failure
RestartSec=3
StandardOutput=append:/tmp/agent-consumer.service.log
StandardError=append:/tmp/agent-consumer.service.err

[Install]
WantedBy=default.target
SERVICE

echo "Step 7: Reloading systemd user daemon..."
systemctl --user daemon-reload

echo "Step 8: Enabling and starting services..."
systemctl --user enable --now agent-api.service
systemctl --user enable --now agent-consumer.service

echo "Step 9: Checking service status..."
systemctl --user status agent-api.service || true
systemctl --user status agent-consumer.service || true

echo "✓ RCA services installed successfully!"
REMOTE_SCRIPT

echo ""
echo "=== Installation completed ==="
echo "Services installed on $HOMELAB_HOST"
