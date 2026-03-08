#!/bin/bash
# ============================================================
# Setup NVIDIA GPU Exporter for Prometheus + Grafana
# Target: homelab (192.168.15.2) — Dual GPU (RTX 2060 SUPER + GTX 1050)
# Exporter: utkuozdemir/nvidia_gpu_exporter (port 9835)
# ============================================================
set -e

HOMELAB_HOST="192.168.15.2"
HOMELAB_USER="homelab"
SSH_KEY="/home/edenilson/.ssh/id_rsa_eddie"
SSH_CMD="ssh -i $SSH_KEY -o ConnectTimeout=15 -o StrictHostKeyChecking=no $HOMELAB_USER@$HOMELAB_HOST"
EXPORTER_VERSION="1.2.1"
EXPORTER_PORT="9835"

echo "🎯 Setup NVIDIA GPU Exporter for Prometheus"
echo "============================================"
echo "Host:     $HOMELAB_HOST"
echo "Exporter: nvidia_gpu_exporter v$EXPORTER_VERSION"
echo "Port:     $EXPORTER_PORT"
echo ""

# --- Step 1: Verificar nvidia-smi ---
echo "📊 Step 1: Verificando nvidia-smi..."
$SSH_CMD "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader" 2>/dev/null
echo "✅ nvidia-smi OK"
echo ""

# --- Step 2: Instalar nvidia_gpu_exporter ---
echo "📦 Step 2: Instalando nvidia_gpu_exporter..."
$SSH_CMD bash << 'REMOTE_INSTALL'
set -e

EXPORTER_VERSION="1.2.1"
EXPORTER_PORT="9835"
BIN_PATH="/usr/local/bin/nvidia_gpu_exporter"

# Check if already running
if systemctl is-active nvidia-gpu-exporter >/dev/null 2>&1; then
    echo "⚠️  nvidia-gpu-exporter já está rodando"
    curl -s http://localhost:$EXPORTER_PORT/metrics | head -5
    exit 0
fi

# Download binary
DOWNLOAD_URL="https://github.com/utkuozdemir/nvidia_gpu_exporter/releases/download/v${EXPORTER_VERSION}/nvidia_gpu_exporter_${EXPORTER_VERSION}_linux_amd64.tar.gz"
echo "  Baixando de: $DOWNLOAD_URL"
cd /tmp
curl -sL "$DOWNLOAD_URL" -o nvidia_gpu_exporter.tar.gz
tar xzf nvidia_gpu_exporter.tar.gz nvidia_gpu_exporter
sudo mv nvidia_gpu_exporter "$BIN_PATH"
sudo chmod +x "$BIN_PATH"
rm -f nvidia_gpu_exporter.tar.gz
echo "  ✅ Binário instalado em $BIN_PATH"

# Create systemd service
sudo tee /etc/systemd/system/nvidia-gpu-exporter.service > /dev/null << 'UNIT'
[Unit]
Description=NVIDIA GPU Exporter for Prometheus
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/nvidia_gpu_exporter --web.listen-address=:9835
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable nvidia-gpu-exporter
sudo systemctl start nvidia-gpu-exporter

# Verify
sleep 2
if curl -s http://localhost:$EXPORTER_PORT/metrics | grep -q "nvidia_smi"; then
    echo "  ✅ Exporter rodando na porta $EXPORTER_PORT"
    METRIC_COUNT=$(curl -s http://localhost:$EXPORTER_PORT/metrics | grep -c "^nvidia_smi_" || true)
    echo "  📊 $METRIC_COUNT métricas GPU disponíveis"
else
    echo "  ❌ Exporter não respondeu"
    sudo journalctl -u nvidia-gpu-exporter --no-pager -n 10
    exit 1
fi
REMOTE_INSTALL

echo "✅ Exporter instalado e rodando"
echo ""

# --- Step 3: Adicionar job no Prometheus ---
echo "⚙️  Step 3: Configurando Prometheus..."
$SSH_CMD bash << 'REMOTE_PROM'
set -e

PROM_CONFIG="/etc/prometheus/prometheus.yml"
EXPORTER_PORT="9835"

if ! test -f "$PROM_CONFIG"; then
    echo "  ❌ $PROM_CONFIG não encontrado"
    exit 1
fi

# Check if job already exists
if grep -q "nvidia-gpu-exporter" "$PROM_CONFIG"; then
    echo "  ⚠️  Job nvidia-gpu-exporter já existe no prometheus.yml"
else
    echo "  Adicionando job nvidia-gpu-exporter..."
    sudo cp "$PROM_CONFIG" "${PROM_CONFIG}.bak.$(date +%Y%m%d%H%M)"
    
    # Append job
    sudo tee -a "$PROM_CONFIG" > /dev/null << JOB

  - job_name: 'nvidia-gpu-exporter'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:$EXPORTER_PORT']
        labels:
          instance: 'homelab'
JOB
    echo "  ✅ Job adicionado"
    
    # Reload prometheus
    if systemctl is-active prometheus >/dev/null 2>&1; then
        sudo systemctl reload prometheus 2>/dev/null || sudo systemctl restart prometheus
        echo "  ✅ Prometheus recarregado"
    elif docker ps --format '{{.Names}}' | grep -q prometheus; then
        docker kill -s SIGHUP $(docker ps -q --filter name=prometheus) 2>/dev/null || true
        echo "  ✅ Prometheus container recarregado"
    fi
fi

# Verify scrape works
sleep 3
UP=$(curl -s "http://localhost:9090/api/v1/query?query=up{job='nvidia-gpu-exporter'}" 2>/dev/null | python3 -c "import sys,json; r=json.loads(sys.stdin.read()); print(r.get('data',{}).get('result',[{}])[0].get('value',['','0'])[1])" 2>/dev/null || echo "0")
if [ "$UP" = "1" ]; then
    echo "  ✅ Prometheus scraping GPU metrics (up=1)"
else
    echo "  ⏳ Prometheus ainda não scrapeou (pode levar ~15s)"
fi
REMOTE_PROM

echo "✅ Prometheus configurado"
echo ""

# --- Step 4: Summary ---
echo "============================================"
echo "✅ Setup completo!"
echo ""
echo "🔗 Verificar métricas:"
echo "  curl http://$HOMELAB_HOST:$EXPORTER_PORT/metrics | grep nvidia_smi"
echo ""
echo "🔗 Verificar no Prometheus:"
echo "  curl 'http://$HOMELAB_HOST:9090/api/v1/query?query=nvidia_smi_gpu_temp'"
echo ""
echo "📌 Próximo passo: adicionar painéis GPU no Grafana"
