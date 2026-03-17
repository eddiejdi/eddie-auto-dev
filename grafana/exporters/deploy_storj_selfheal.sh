#!/usr/bin/env bash
# Deploy Storj self-healing exporter + Grafana/Prometheus provisioning to homelab
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_REPO="/home/homelab/eddie-auto-dev"

echo "=== Deploying Storj self-healing to $HOMELAB ==="

echo "[1/6] Syncing exporter files..."
ssh "$HOMELAB" "mkdir -p $REMOTE_REPO/grafana/exporters"
scp "$REPO_DIR/grafana/exporters/storj_selfheal_exporter.py" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/storj_selfheal_config.json" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/storj-selfheal-exporter.service" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"

echo "[2/6] Installing Python dependency..."
ssh "$HOMELAB" "
  /home/homelab/venv/bin/pip install prometheus_client 2>/dev/null || \
  pip3 install prometheus_client 2>/dev/null || true
"

echo "[3/6] Installing self-heal config + systemd service..."
ssh "$HOMELAB" "
  sudo mkdir -p /etc/eddie /var/lib/eddie/storj-heal
  sudo cp $REMOTE_REPO/grafana/exporters/storj_selfheal_config.json /etc/eddie/storj_selfheal.json
  sudo cp $REMOTE_REPO/grafana/exporters/storj-selfheal-exporter.service /etc/systemd/system/storj-selfheal-exporter.service
  sudo systemctl daemon-reload
  sudo systemctl enable storj-selfheal-exporter.service
  sudo systemctl restart storj-selfheal-exporter.service
"

echo "[4/6] Syncing Prometheus + Grafana provisioning files..."
scp "$REPO_DIR/monitoring/prometheus.yml" "$HOMELAB:$REMOTE_REPO/monitoring/prometheus.yml"
scp "$REPO_DIR/monitoring/grafana/provisioning/alerting/rules.yml" "$HOMELAB:$REMOTE_REPO/monitoring/grafana/provisioning/alerting/rules.yml"
scp "$REPO_DIR/deploy/grafana-storj-dashboard.json" "$HOMELAB:$REMOTE_REPO/deploy/grafana-storj-dashboard.json"
ssh "$HOMELAB" "
  sudo cp $REMOTE_REPO/monitoring/prometheus.yml /home/homelab/monitoring/prometheus.yml
  sudo cp $REMOTE_REPO/monitoring/grafana/provisioning/alerting/rules.yml /home/homelab/monitoring/grafana/provisioning/alerting/rules.yml
  sudo cp $REMOTE_REPO/deploy/grafana-storj-dashboard.json /home/homelab/monitoring/grafana/provisioning/dashboards/storj-node-dashboard.json
"

echo "[5/6] Restarting Prometheus + Grafana..."
ssh "$HOMELAB" "
  docker restart prometheus >/dev/null
  docker restart grafana >/dev/null
"

echo "[6/6] Verifying endpoints..."
ssh "$HOMELAB" "
  sudo systemctl --no-pager --full status storj-selfheal-exporter.service || true
  echo '--- storj-selfheal metrics ---'
  curl -s http://127.0.0.1:9652/metrics | grep -E '^storj_selfheal_' | head -20 || true
  echo '--- storj-selfheal status ---'
  curl -s http://127.0.0.1:9653/status || true
  echo
  echo '--- prometheus query ---'
  curl -sG --data-urlencode 'query=storj_selfheal_healthy' http://127.0.0.1:9090/api/v1/query || true
"

echo ""
echo "Deploy complete."
