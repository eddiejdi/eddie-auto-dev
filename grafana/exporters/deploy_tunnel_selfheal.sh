#!/usr/bin/env bash
# Deploy tunnel self-healing exporter to homelab
# Usage: bash deploy_tunnel_selfheal.sh [homelab_host]
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_REPO="/home/homelab/eddie-auto-dev"

echo "=== Deploying Tunnel Self-Healing to $HOMELAB ==="

# 1. Sync exporter files
echo "[1/6] Syncing exporter files..."
ssh "$HOMELAB" "mkdir -p $REMOTE_REPO/grafana/exporters $REMOTE_REPO/grafana/dashboards"
scp "$REPO_DIR/grafana/exporters/tunnel_healthcheck_exporter.py" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/tunnel_healthcheck_config.json" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/exporters/tunnel-healthcheck-exporter.service" "$HOMELAB:$REMOTE_REPO/grafana/exporters/"
scp "$REPO_DIR/grafana/dashboards/tunnel-selfheal.json" "$HOMELAB:$REMOTE_REPO/grafana/dashboards/"

# 2. Install Python dependency
echo "[2/6] Installing prometheus_client..."
ssh "$HOMELAB" "
  pip3 install prometheus_client 2>/dev/null || \
  /home/homelab/venv/bin/pip install prometheus_client 2>/dev/null || \
  sudo pip3 install prometheus_client 2>/dev/null || \
  echo 'WARNING: Could not install prometheus_client — install manually'
"

# 3. Deploy config
echo "[3/6] Deploying tunnel config..."
ssh "$HOMELAB" "
  sudo mkdir -p /etc/eddie /var/lib/eddie/tunnel-heal
  sudo cp $REMOTE_REPO/grafana/exporters/tunnel_healthcheck_config.json /etc/eddie/tunnel_healthcheck.json
  sudo chown root:root /etc/eddie/tunnel_healthcheck.json
"

# 4. Deploy systemd service
echo "[4/6] Installing systemd service..."
ssh "$HOMELAB" "
  sudo cp $REMOTE_REPO/grafana/exporters/tunnel-healthcheck-exporter.service \
    /etc/systemd/system/tunnel-healthcheck-exporter.service
  sudo systemctl daemon-reload
  sudo systemctl enable tunnel-healthcheck-exporter.service
  sudo systemctl restart tunnel-healthcheck-exporter.service
"

# 5. Verify
echo "[5/6] Verifying service..."
sleep 3
ssh "$HOMELAB" "
  sudo systemctl status tunnel-healthcheck-exporter.service --no-pager || true
  echo '---'
  echo 'Prometheus metrics:'
  curl -s http://127.0.0.1:9110/metrics 2>/dev/null | head -20 || echo '(waiting for metrics...)'
  echo '---'
  echo 'Status API:'
  curl -s http://127.0.0.1:9111/status 2>/dev/null || echo '(waiting for status...)'
"

# 6. Add Prometheus scrape config (if prometheus.yml is managed locally)
echo "[6/6] Adding Prometheus scrape target..."
ssh "$HOMELAB" "
  PROM_CFG='/etc/prometheus/prometheus.yml'
  if [ -f \"\$PROM_CFG\" ]; then
    if ! grep -q 'tunnel-healthcheck' \"\$PROM_CFG\"; then
      sudo tee -a \"\$PROM_CFG\" > /dev/null << 'SCRAPE'

  # Tunnel self-healing exporter
  - job_name: 'tunnel-healthcheck'
    static_configs:
      - targets: ['localhost:9110']
    scrape_interval: 15s
    scrape_timeout: 10s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'tunnel-heal-9110'
SCRAPE
      echo 'Added tunnel-healthcheck to prometheus.yml'
      sudo systemctl reload prometheus 2>/dev/null || echo 'Prometheus reload skipped (may need manual reload)'
    else
      echo 'tunnel-healthcheck already in prometheus.yml'
    fi
  else
    echo 'No /etc/prometheus/prometheus.yml found — add scrape target manually'
  fi
"

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Endpoints on homelab:"
echo "  Prometheus metrics: http://192.168.15.2:9110/metrics"
echo "  Status API:         http://192.168.15.2:9111/status"
echo "  Audit log:          http://192.168.15.2:9111/audit"
echo ""
echo "Grafana dashboard: import grafana/dashboards/tunnel-selfheal.json"
echo "  or copy to Grafana provisioning directory on homelab"
