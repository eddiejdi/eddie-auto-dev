#!/usr/bin/env bash
# Install RCA scripts and systemd user services on self-hosted runner.
# Called from deploy-to-homelab workflow.
set -e

echo "Installing RCA scripts to $HOME/eddie-auto-dev/tools/homelab_recovery"
mkdir -p "$HOME/eddie-auto-dev/tools/homelab_recovery"
cp -r tools/homelab_recovery/* "$HOME/eddie-auto-dev/tools/homelab_recovery/" || true
cp -f tools/agent_api_client.py "$HOME/eddie-auto-dev/tools/" || true

# create user systemd units
mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/agent-api.service" <<'SERVICE'
[Unit]
Description=Agent RCA API (user)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 $HOME/eddie-auto-dev/tools/homelab_recovery/simple_agent_api.py
Restart=on-failure
RestartSec=3
StandardOutput=append:/tmp/agent-api.service.log
StandardError=append:/tmp/agent-api.service.err

[Install]
WantedBy=default.target
SERVICE

cat > "$HOME/.config/systemd/user/agent-consumer.service" <<'SERVICE'
[Unit]
Description=Agent Consumer (user) - process RCAs from /tmp/agent_queue
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 $HOME/eddie-auto-dev/tools/homelab_recovery/agent_consumer_loop.py
Restart=always
RestartSec=5
StandardOutput=append:/tmp/agent-consumer.service.log
StandardError=append:/tmp/agent-consumer.service.err

[Install]
WantedBy=default.target
SERVICE

# enable and start user services (best-effort)
systemctl --user daemon-reload || true
systemctl --user enable --now agent-api.service || true
systemctl --user enable --now agent-consumer.service || true
echo "✅ RCA services installed"
