#!/bin/bash
###############################################################################
# AutoCoinBot - Setup Grafana Dashboard
# Configura Prometheus, Grafana e dashboards para monitoramento
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/autocoinbot-monitoring"
PROMETHEUS_PORT=9091
EXPORTER_PORT=9090
GRAFANA_PORT=3001

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     🤖 AutoCoinBot - Grafana Dashboard Setup              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "⚠️  Please do not run as root. Will use sudo when needed."
    exit 1
fi

# Step 1: Install Prometheus (if not installed)
echo "📦 Step 1: Checking Prometheus..."
if ! command -v prometheus &> /dev/null; then
    echo "   Installing Prometheus..."
    
    # Download Prometheus
    PROM_VERSION="2.40.0"
    cd /tmp
    wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    tar xzf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    
    # Install
    sudo mkdir -p /opt/prometheus
    sudo cp prometheus-${PROM_VERSION}.linux-amd64/prometheus /usr/local/bin/
    sudo cp prometheus-${PROM_VERSION}.linux-amd64/promtool /usr/local/bin/
    sudo mkdir -p /etc/prometheus
    sudo mkdir -p /var/lib/prometheus
    
    # Cleanup
    rm -rf prometheus-*
    
    echo "   ✅ Prometheus installed"
else
    echo "   ✅ Prometheus already installed"
fi

# Step 2: Configure Prometheus
echo ""
echo "⚙️  Step 2: Configuring Prometheus..."

sudo tee /etc/prometheus/prometheus.yml > /dev/null <<EOF
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: 'autocoinbot'
    static_configs:
      - targets: ['localhost:${EXPORTER_PORT}']
        labels:
          instance: 'autocoinbot-agent'
          env: 'production'
EOF

echo "   ✅ Prometheus configured"

# Step 3: Create Prometheus systemd service
echo ""
echo "🔧 Step 3: Creating Prometheus service..."

sudo tee /etc/systemd/system/autocoinbot-prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus for AutoCoinBot
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/prometheus \\
  --config.file=/etc/prometheus/prometheus.yml \\
  --storage.tsdb.path=/var/lib/prometheus \\
  --web.listen-address=127.0.0.1:${PROMETHEUS_PORT} \\
  --web.console.templates=/etc/prometheus/consoles \\
  --web.console.libraries=/etc/prometheus/console_libraries
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "   ✅ Prometheus service created"

# Step 4: Create exporter systemd service
echo ""
echo "🔧 Step 4: Creating Prometheus Exporter service..."

sudo tee /etc/systemd/system/autocoinbot-exporter.service > /dev/null <<EOF
[Unit]
Description=Prometheus Exporter for AutoCoinBot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/../.venv/bin/python3 ${SCRIPT_DIR}/prometheus_exporter.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "   ✅ Exporter service created"

# Step 5: Install Grafana (if not installed)
echo ""
echo "📦 Step 5: Checking Grafana..."
if ! command -v grafana-server &> /dev/null; then
    echo "   Installing Grafana..."
    
    # Add Grafana repository
    sudo apt-get install -y apt-transport-https software-properties-common wget
    wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
    echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
    
    sudo apt-get update
    sudo apt-get install -y grafana
    
    echo "   ✅ Grafana installed"
else
    echo "   ✅ Grafana already installed"
fi

# Step 6: Configure Grafana
echo ""
echo "⚙️  Step 6: Configuring Grafana..."

# Set custom port
sudo sed -i "s/;http_port = 3000/http_port = ${GRAFANA_PORT}/" /etc/grafana/grafana.ini

# Configure datasource
sudo mkdir -p /etc/grafana/provisioning/datasources
sudo tee /etc/grafana/provisioning/datasources/prometheus.yaml > /dev/null <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:${PROMETHEUS_PORT}
    isDefault: true
    editable: true
EOF

# Configure dashboard
sudo mkdir -p /etc/grafana/provisioning/dashboards
sudo tee /etc/grafana/provisioning/dashboards/autocoinbot.yaml > /dev/null <<EOF
apiVersion: 1

providers:
  - name: 'AutoCoinBot'
    orgId: 1
    folder: 'Trading'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: ${SCRIPT_DIR}
EOF

echo "   ✅ Grafana configured"

# Step 7: Start services
echo ""
echo "🚀 Step 7: Starting services..."

sudo systemctl enable autocoinbot-exporter
sudo systemctl start autocoinbot-exporter
echo "   ✅ Exporter started"

sudo systemctl enable autocoinbot-prometheus
sudo systemctl start autocoinbot-prometheus
echo "   ✅ Prometheus started"

sudo systemctl enable grafana-server
sudo systemctl restart grafana-server
echo "   ✅ Grafana started"

# Step 8: Wait for services
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Step 9: Check services
echo ""
echo "🔍 Step 9: Checking services status..."
echo ""

if systemctl is-active --quiet autocoinbot-exporter; then
    echo "   ✅ Exporter:    RUNNING"
else
    echo "   ❌ Exporter:    FAILED"
fi

if systemctl is-active --quiet autocoinbot-prometheus; then
    echo "   ✅ Prometheus:  RUNNING"
else
    echo "   ❌ Prometheus:  FAILED"
fi

if systemctl is-active --quiet grafana-server; then
    echo "   ✅ Grafana:     RUNNING"
else
    echo "   ❌ Grafana:     FAILED"
fi

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETED                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Access Points:"
echo "   • Grafana Dashboard: http://localhost:${GRAFANA_PORT}"
echo "   • Prometheus:        http://localhost:${PROMETHEUS_PORT}"
echo "   • Metrics Exporter:  http://localhost:${EXPORTER_PORT}/metrics"
echo ""
echo "🔐 Grafana Login:"
echo "   • Username: admin"
echo "   • Password: admin (change on first login)"
echo ""
echo "📁 Dashboard:"
echo "   • Name: 🤖 AutoCoinBot - Trading Dashboard"
echo "   • UID:  autocoinbot-trading"
echo ""
echo "🛠️  Useful Commands:"
echo "   • View logs:     sudo journalctl -u autocoinbot-exporter -f"
echo "   • Restart:       sudo systemctl restart autocoinbot-exporter"
echo "   • Stop:          sudo systemctl stop autocoinbot-exporter"
echo "   • Check status:  sudo systemctl status autocoinbot-exporter"
echo ""
echo "🎯 Next Steps:"
echo "   1. Open Grafana at http://localhost:${GRAFANA_PORT}"
echo "   2. Login with admin/admin"
echo "   3. Navigate to Dashboards → Trading → AutoCoinBot"
echo "   4. Enjoy real-time monitoring! 🚀"
echo ""
