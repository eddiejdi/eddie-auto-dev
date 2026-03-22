#!/usr/bin/env bash
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_REPO="/home/homelab/shared-auto-dev"

echo "=== Deploying Nextcloud Self-Healing to $HOMELAB ==="

echo "[1/7] Syncing files..."
ssh "$HOMELAB" "mkdir -p $REMOTE_REPO/grafana/exporters $REMOTE_REPO/grafana/dashboards $REMOTE_REPO/monitoring/grafana"
scp "$REPO_DIR/grafana/exporters/nextcloud_selfheal_exporter.py" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/nextcloud_selfheal_config.json" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/nextcloud-selfheal-exporter.service" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/dashboards/nextcloud-rpa4all-selfheal.json" "$HOMELAB:$REMOTE_REPO/grafana/dashboards/"
scp "$REPO_DIR/monitoring/grafana/setup-nextcloud-dashboard.sh" "$HOMELAB:$REMOTE_REPO/monitoring/grafana/"

echo "[2/7] Installing Python dependencies..."
ssh "$HOMELAB" "
  /home/homelab/venv/bin/pip install prometheus_client requests 2>/dev/null || \
  pip3 install --user prometheus_client requests 2>/dev/null || \
  echo 'WARNING: install dependencies manually'
"

echo "[3/7] Deploying config..."
ssh "$HOMELAB" "
  sudo mkdir -p /etc/shared /var/lib/shared/nextcloud-heal
  sudo cp $REMOTE_REPO/grafana/exporters/nextcloud_selfheal_config.json /etc/shared/nextcloud_selfheal.json
  sudo chown root:root /etc/shared/nextcloud_selfheal.json
"

echo "[4/7] Installing systemd service..."
ssh "$HOMELAB" "
  sudo cp $REMOTE_REPO/grafana/exporters/nextcloud-selfheal-exporter.service /etc/systemd/system/nextcloud-selfheal-exporter.service
  sudo systemctl daemon-reload
  sudo systemctl enable nextcloud-selfheal-exporter.service
  sudo systemctl restart nextcloud-selfheal-exporter.service
"

echo "[5/7] Updating Prometheus scrape config..."
ssh "$HOMELAB" "
  PROM_CFG='/etc/prometheus/prometheus.yml'
  if [ -f \"\$PROM_CFG\" ] && ! grep -q \"nextcloud-selfheal\" \"\$PROM_CFG\"; then
    sudo tee -a \"\$PROM_CFG\" > /dev/null << 'SCRAPE'

  - job_name: 'nextcloud-selfheal'
    static_configs:
      - targets: ['localhost:9130']
    scrape_interval: 15s
    scrape_timeout: 10s
SCRAPE
    sudo systemctl reload prometheus 2>/dev/null || true
  fi
"

echo "[6/7] Verifying service..."
sleep 3
ssh "$HOMELAB" "
  sudo systemctl status nextcloud-selfheal-exporter.service --no-pager || true
  echo '--- metrics ---'
  curl -s http://127.0.0.1:9130/metrics | head -30 || true
  echo '--- status ---'
  curl -s http://127.0.0.1:9131/status || true
"

echo "[7/7] Importing dashboard..."
ssh "$HOMELAB" "chmod +x $REMOTE_REPO/monitoring/grafana/setup-nextcloud-dashboard.sh && $REMOTE_REPO/monitoring/grafana/setup-nextcloud-dashboard.sh || true"

echo "Deploy complete."
