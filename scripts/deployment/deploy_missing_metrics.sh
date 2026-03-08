#!/bin/bash
#
# Deploy Shared Central Missing Metrics Exporter
# Instala e configura o exporter de métricas faltantes
#

set -e

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🚀 DEPLOY — Shared Central Missing Metrics Exporter"
echo "════════════════════════════════════════════════════════════════════════════════"

# Configurações
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"
HOMELAB_SSH_KEY="${HOMELAB_SSH_KEY:-~/.ssh/id_rsa}"
SERVICE_NAME="shared-central-metrics"
EXPORTER_PORT="9104"
DATABASE_URL="${DATABASE_URL:-postgresql://postgress:shared_memory_2026@localhost:5432/postgres}"

echo ""
echo "📋 Configuração:"
echo "   Host: $HOMELAB_HOST"
echo "   User: $HOMELAB_USER"
echo "   Service: $SERVICE_NAME"
echo "   Port: $EXPORTER_PORT"
echo ""

# Verificar se está no diretório correto
if [ ! -f "shared_central_missing_metrics.py" ]; then
    echo "❌ Erro: shared_central_missing_metrics.py não encontrado"
    echo "   Execute este script no diretório raiz do projeto"
    exit 1
fi

echo "1️⃣  Copiando script para homelab..."
scp -i "$HOMELAB_SSH_KEY" shared_central_missing_metrics.py \
    "$HOMELAB_USER@$HOMELAB_HOST:~/shared-auto-dev/" || {
    echo "❌ Erro ao copiar script. Verifique conectividade SSH."
    exit 1
}
echo "✅ Script copiado"

echo ""
echo "2️⃣  Criando systemd service..."

# Criar service file
SERVICE_CONTENT="[Unit]
Description=Shared Central Missing Metrics Exporter
After=network.target postgresql.service

[Service]
Type=simple
User=$HOMELAB_USER
WorkingDirectory=/home/$HOMELAB_USER/shared-auto-dev
Environment=\"DATABASE_URL=$DATABASE_URL\"
Environment=\"MISSING_METRICS_PORT=$EXPORTER_PORT\"
ExecStart=/home/$HOMELAB_USER/shared-auto-dev/.venv/bin/python3 shared_central_missing_metrics.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"

# Criar arquivo temporário local
echo "$SERVICE_CONTENT" > /tmp/${SERVICE_NAME}.service

# Copiar para homelab e instalar
scp -i "$HOMELAB_SSH_KEY" /tmp/${SERVICE_NAME}.service \
    "$HOMELAB_USER@$HOMELAB_HOST:/tmp/" || {
    echo "❌ Erro ao copiar service file"
    exit 1
}

ssh -i "$HOMELAB_SSH_KEY" "$HOMELAB_USER@$HOMELAB_HOST" << 'EOF'
    sudo mv /tmp/shared-central-metrics.service /etc/systemd/system/
    sudo chmod 644 /etc/systemd/system/shared-central-metrics.service
    sudo systemctl daemon-reload
EOF

echo "✅ Service criado"

echo ""
echo "3️⃣  Ativando service..."
ssh -i "$HOMELAB_SSH_KEY" "$HOMELAB_USER@$HOMELAB_HOST" << 'EOF'
    sudo systemctl enable shared-central-metrics
    sudo systemctl restart shared-central-metrics
    sleep 2
    sudo systemctl status shared-central-metrics --no-pager || true
EOF

echo ""
echo "4️⃣  Verificando métricas..."
sleep 3

# Verificar se métricas estão disponíveis
ssh -i "$HOMELAB_SSH_KEY" "$HOMELAB_USER@$HOMELAB_HOST" << 'EOF'
    if curl -s http://localhost:9102/metrics | grep -q "agent_count_total"; then
        echo "✅ agent_count_total disponível"
    else
        echo "⚠️  agent_count_total NÃO disponível"
    fi
    
    if curl -s http://localhost:9102/metrics | grep -q "message_rate_total"; then
        echo "✅ message_rate_total disponível"
    else
        echo "⚠️  message_rate_total NÃO disponível"
    fi
EOF

echo ""
echo "5️⃣  Configurando Prometheus scrape..."

# Criar job de scrape
PROMETHEUS_JOB="
  # Shared Central Missing Metrics
  - job_name: 'shared_central_metrics'
    static_configs:
      - targets: ['localhost:9102']
    scrape_interval: 30s
"

echo "$PROMETHEUS_JOB" > /tmp/prometheus_job.yml
echo "📝 Job criado em /tmp/prometheus_job.yml"
echo ""
echo "⚠️  AÇÃO MANUAL NECESSÁRIA:"
echo "   1. Adicione o seguinte job em /etc/prometheus/prometheus.yml:"
echo ""
cat /tmp/prometheus_job.yml
echo ""
echo "   2. Reload Prometheus:"
echo "      sudo systemctl reload prometheus"
echo ""

echo "════════════════════════════════════════════════════════════════════════════════"
echo "✅ DEPLOY CONCLUÍDO"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Status:"
echo "   Service: sudo systemctl status shared-central-metrics"
echo "   Logs: sudo journalctl -u shared-central-metrics -f"
echo "   Métricas: curl http://$HOMELAB_HOST:9102/metrics"
echo ""
echo "🔄 Próximos passos:"
echo "   1. Configurar Prometheus scrape (ver mensagem acima)"
echo "   2. Validar dashboard: python3 validate_shared_central_api.py"
echo "   3. Verificar Grafana: https://grafana.rpa4all.com/d/shared-central/"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
