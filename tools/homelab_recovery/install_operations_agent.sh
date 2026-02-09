#!/bin/bash
set -euo pipefail

echo "=== Installing Operations Agent service on homelab ==="

HOST="homelab@192.168.15.2"
REMOTE_DIR="/home/homelab/eddie-auto-dev"

echo "Step 1: Transferring operations_agent.py..."
scp tools/operations_agent.py "$HOST:$REMOTE_DIR/tools/"

echo "Step 2: Installing systemd user service..."
ssh "$HOST" bash <<'REMOTE'
    set -euo pipefail
    
    # Ensure directories exist
    mkdir -p ~/.config/systemd/user
    
    # Create service file
    cat > ~/.config/systemd/user/operations-agent.service <<'SERVICE'
[Unit]
Description=Operations Agent - RCA remediation handler
After=network.target agent-api.service

[Service]
Type=simple
WorkingDirectory=/home/homelab/eddie-auto-dev
Environment="PYTHONPATH=/home/homelab/eddie-auto-dev"
Environment="AGENT_API_URL=http://127.0.0.1:8888"
Environment="ALLOW_AGENT_API=1"
Environment="DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres"
Environment="OPS_AGENT_POLL=10"
Environment="AUTONOMOUS_MODE=0"
ExecStart=/home/homelab/eddie-auto-dev/.venv/bin/python3 -u /home/homelab/eddie-auto-dev/tools/operations_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
SERVICE
    
    # Reload daemon and enable service
    systemctl --user daemon-reload
    systemctl --user enable operations-agent.service
    systemctl --user start operations-agent.service
    
    # Wait a moment
    sleep 2
    
    # Check status
    echo "=== Operations Agent Status ==="
    systemctl --user status operations-agent.service --no-pager || true
REMOTE

echo ""
echo "✓ Operations Agent service installed and started"
echo "  Check logs: ssh homelab@192.168.15.2 'journalctl --user -u operations-agent -f'"
