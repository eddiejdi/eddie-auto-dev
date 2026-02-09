#!/bin/bash
# Fix Prometheus systemd startup on homelab
# Run this script directly on the homelab server via SSH or local terminal

set -e

echo "[1/4] Creating Prometheus data directories..."
sudo mkdir -p /var/lib/prometheus/metrics2
sudo mkdir -p /var/lib/prometheus/wal

echo "[2/4] Fixing ownership and permissions..."
sudo chown -R prometheus:prometheus /var/lib/prometheus
sudo chmod -R 755 /var/lib/prometheus

echo "[3/4] Configuring Prometheus scrape config..."
sudo tee /etc/prometheus/prometheus.yml > /dev/null << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'homelab'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'agent-network-exporter'
    static_configs:
      - targets: ['127.0.0.1:9101']
    scrape_interval: 10s
    scrape_timeout: 5s
EOF

echo "[4/4] Restarting Prometheus service..."
sudo systemctl restart prometheus
sleep 2

echo "✓ Checking service status..."
if sudo systemctl is-active prometheus > /dev/null 2>&1; then
    echo "✓ Prometheus is RUNNING"
    echo ""
    echo "Health check:"
    curl -s http://localhost:9090/-/healthy && echo "✓ API responsive" || echo "✗ API not responding"
    echo ""
    echo "Agent metrics check:"
    RESULTS=$(curl -s 'http://localhost:9090/api/v1/query?query=up{job="agent-network-exporter"}' 2>/dev/null | grep -o '"value":\[[^]]*\]' | head -1)
    if [ -n "$RESULTS" ]; then
        echo "✓ Agent metrics found: $RESULTS"
    else
        echo "⚠ No metrics yet (scraping...)"
    fi
else
    echo "✗ Prometheus FAILED TO START"
    echo "Logs:"
    sudo journalctl -u prometheus -n 20 --no-pager
    exit 1
fi
