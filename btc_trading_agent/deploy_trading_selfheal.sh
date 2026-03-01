#!/usr/bin/env bash
# Deploy trading agent self-healing exporter to homelab with Ollama integration
# Usage: bash deploy_trading_selfheal.sh [homelab_host]
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_REPO="/home/homelab/eddie-auto-dev"
REMOTE_DATA="/var/lib/eddie/trading-heal"

echo "=== Deploying Trading Agent Self-Healing to $HOMELAB ==="

# 1. Create data directory
echo "[1/8] Creating data directory..."
ssh "$HOMELAB" "sudo mkdir -p $REMOTE_DATA && sudo chown homelab:homelab $REMOTE_DATA && chmod 755 $REMOTE_DATA"

# 2. Sync exporter files
echo "[2/8] Syncing exporter files..."
ssh "$HOMELAB" "mkdir -p $REMOTE_REPO/btc_trading_agent/systemd"
scp "$REPO_DIR/btc_trading_agent/trading_selfheal_exporter.py" "$HOMELAB:$REMOTE_REPO/btc_trading_agent/"
scp "$REPO_DIR/btc_trading_agent/trading_selfheal_config.json" "$HOMELAB:$REMOTE_REPO/btc_trading_agent/"
scp "$REPO_DIR/btc_trading_agent/systemd/trading-selfheal-exporter.service" "$HOMELAB:$REMOTE_REPO/btc_trading_agent/systemd/"

# 3. Install Python dependencies
echo "[3/8] Installing Python dependencies..."
ssh "$HOMELAB" "
  pip3 install --upgrade psycopg2-binary prometheus_client httpx 2>/dev/null || \
  /home/homelab/.venv/bin/pip install --upgrade psycopg2-binary prometheus_client httpx 2>/dev/null || \
  sudo pip3 install --upgrade psycopg2-binary prometheus_client httpx 2>/dev/null || \
  echo 'WARNING: Could not install some packages — install manually if needed'
"

# 4. Deploy systemd service
echo "[4/8] Deploying systemd service..."
ssh "$HOMELAB" "
  sudo cp $REMOTE_REPO/btc_trading_agent/systemd/trading-selfheal-exporter.service /etc/systemd/system/
  sudo systemctl daemon-reload
"

# 5. Configure sudoers for self-heal restarts
echo "[5/8] Configuring sudoers for self-healing restarts..."
ssh "$HOMELAB" "
  echo 'homelab ALL=(ALL) NOPASSWD: /bin/systemctl restart crypto-agent@*' | \
  sudo tee /etc/sudoers.d/trading-selfheal-restart >/dev/null && \
  sudo chmod 440 /etc/sudoers.d/trading-selfheal-restart && \
  echo '✅ Sudoers configured'
"

# 6. Update Prometheus config
echo "[6/8] Updating Prometheus configuration..."
echo "  - Syncing prometheus.yml..."
scp "$REPO_DIR/monitoring/prometheus.yml" "$HOMELAB:/tmp/prometheus.yml.new"
ssh "$HOMELAB" "
  if diff -q /etc/prometheus/prometheus.yml /tmp/prometheus.yml.new >/dev/null 2>&1; then
    echo '  Prometheus config already up to date'
  else
    sudo cp /etc/prometheus/prometheus.yml /etc/prometheus/prometheus.yml.bak
    sudo cp /tmp/prometheus.yml.new /etc/prometheus/prometheus.yml
    sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
    sudo systemctl reload prometheus
    echo '  ✅ Prometheus reloaded with new crypto-exporters scrape config'
  fi
"

# 7. Update alert rules
echo "[7/8] Updating alert rules..."
scp "$REPO_DIR/monitoring/alert_rules.yml" "$HOMELAB:/tmp/alert_rules.yml.new"
ssh "$HOMELAB" "
  sudo cp /etc/prometheus/alert_rules.yml /etc/prometheus/alert_rules.yml.bak 2>/dev/null || true
  sudo cp /tmp/alert_rules.yml.new /etc/prometheus/alert_rules.yml
  sudo chown prometheus:prometheus /etc/prometheus/alert_rules.yml
  sudo systemctl reload prometheus
  echo '  ✅ Alert rules updated and Prometheus reloaded'
"

# 8. Start and enable the service
echo "[8/8] Starting trading-selfheal-exporter service..."
ssh "$HOMELAB" "
  sudo systemctl enable trading-selfheal-exporter.service
  sudo systemctl start trading-selfheal-exporter.service
  sleep 2
  sudo systemctl status trading-selfheal-exporter.service || echo 'WARNING: service might not have started'
"

echo ""
echo "=== ✅ Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Verify service status:"
echo "   ssh $HOMELAB \"sudo systemctl status trading-selfheal-exporter\""
echo ""
echo "2. Check health endpoint:"
echo "   curl -s http://192.168.15.2:9121/status | jq"
echo ""
echo "3. Check audit log:"
echo "   curl -s http://192.168.15.2:9121/audit | jq '.[-10:]'"
echo ""
echo "4. Verify Prometheus targets:"
echo "   curl -s http://192.168.15.2:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job==\"trading-selfheal\" or .labels.job==\"crypto-exporters\")'"
echo ""
echo "5. View Ollama integration status in dashboard:"
echo "   https://grafana.rpa4all.com/d/237610b0-trading-agent-monitor"
echo ""
echo "Environment variables for customization:"
echo "  OLLAMA_ENABLED=true|false (default: true)"
echo "  OLLAMA_HOST=http://192.168.15.2:11434 (default)"
echo "  OLLAMA_MODEL=qwen2.5-coder:7b (default)"
echo "  TRADING_HEAL_STALL_THRESHOLD=600 (seconds, default: 10 min)"
echo "  TRADING_HEAL_MAX_RESTARTS=3 (per hour, default)"
echo ""
echo "Edit /etc/systemd/system/trading-selfheal-exporter.service and restart:"
echo "  sudo systemctl daemon-reload && sudo systemctl restart trading-selfheal-exporter"
