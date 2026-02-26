#!/bin/bash
# Deploy eddie_central_extended_metrics.py para homelab
# Implementa as 11 métricas restantes (FASE 2)

set -e

echo "🚀 Deploy FASE 2 — Métricas Estendidas"
echo "========================================"

HOMELAB_USER="homelab"
HOMELAB_HOST="192.168.15.2"
HOMELAB_PATH="/home/homelab/eddie-auto-dev"
LOCAL_SCRIPT="eddie_central_extended_metrics.py"
REMOTE_SCRIPT="$HOMELAB_PATH/$LOCAL_SCRIPT"
SERVICE_NAME="eddie-central-extended-metrics"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
PORT="9106"

# =========================================================================
# STEP 1: Validar arquivo local
# =========================================================================
echo ""
echo "1️⃣ Validando arquivo local..."
if [ ! -f "$LOCAL_SCRIPT" ]; then
    echo "❌ Arquivo $LOCAL_SCRIPT não encontrado"
    exit 1
fi
echo "✅ Script encontrado: $(wc -l < "$LOCAL_SCRIPT") linhas"

# =========================================================================
# STEP 2: Copiar script para homelab
# =========================================================================
echo ""
echo "2️⃣ Copiando script para homelab..."
scp -i ~/.ssh/id_rsa "$LOCAL_SCRIPT" "$HOMELAB_USER@$HOMELAB_HOST:$REMOTE_SCRIPT"
echo "✅ Script copiado para $REMOTE_SCRIPT"

# =========================================================================
# STEP 3: Tornar executável  
# =========================================================================
echo ""
echo "3️⃣ Configurando permissões..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" \
    "chmod +x $REMOTE_SCRIPT && ls -lh $REMOTE_SCRIPT"

# =========================================================================
# STEP 4: Criar serviço systemd
# =========================================================================
echo ""
echo "4️⃣ Criando serviço systemd..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" << 'SYSTEMD_SETUP'
sudo tee /etc/systemd/system/eddie-central-extended-metrics.service > /dev/null << 'SERVICE'
[Unit]
Description=Eddie Central Extended Metrics Exporter (FASE 2)
After=network.target postgresql.service eddie-central-metrics.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/eddie-auto-dev
ExecStart=/home/homelab/eddie-auto-dev/.venv/bin/python3 -u eddie_central_extended_metrics.py
Environment="EXTENDED_METRICS_PORT=9106"
Environment="DATABASE_URL=postgresql://postgress:eddie_memory_2026@localhost:5432/postgres"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Reload systemd
sudo systemctl daemon-reload
echo "✅ Serviço criado"
SYSTEMD_SETUP

# =========================================================================
# STEP 5: Iniciar serviço
# =========================================================================
echo ""
echo "5️⃣ Iniciando serviço..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" << 'SERVICE_START'
sudo systemctl enable eddie-central-extended-metrics.service
sudo systemctl start eddie-central-extended-metrics.service
sleep 2
sudo systemctl status eddie-central-extended-metrics.service --no-pager || true
SERVICE_START

# =========================================================================
# STEP 6: Verificar porta
# =========================================================================
echo ""
echo "6️⃣ Verificando porta $PORT..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" << 'PORT_CHECK'
sleep 2
curl -s http://localhost:9106/metrics | head -5 || echo "⚠️  Aguardando inicialização..."
sleep 3
curl -s http://localhost:9106/metrics | grep -E "^(conversation|active_conv|agent_memory|ipc_pending|agent_confidence|agent_feedback)" || echo "⚠️  Métricas ainda não atualizadas"
PORT_CHECK

# =========================================================================
# STEP 7: Atualizar Prometheus
# =========================================================================
echo ""
echo "7️⃣ Atualizando Prometheus..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" << 'PROMETHEUS_UPDATE'
PROMETHEUS_CONFIG="/etc/prometheus/prometheus.yml"

# Fazer backup
sudo cp "$PROMETHEUS_CONFIG" "${PROMETHEUS_CONFIG}.backup.$(date +%s)"
echo "✅ Backup do prometheus.yml criado"

# Verificar se job já existe
if ! sudo grep -q "eddie-central-extended" "$PROMETHEUS_CONFIG"; then
    echo "Adicionando job ao prometheus.yml..."
    sudo tee -a "$PROMETHEUS_CONFIG" > /dev/null << 'JOB'

  - job_name: 'eddie-central-extended-metrics'
    static_configs:
      - targets: ['localhost:9106']
JOB
    echo "✅ Job adicionado"
else
    echo "ℹ️  Job já existe"
fi

# Recarregar Prometheus
sudo systemctl reload prometheus || sudo systemctl restart prometheus
sleep 3
echo "✅ Prometheus recarregado"
PROMETHEUS_UPDATE

# =========================================================================
# STEP 8: Validação final
# =========================================================================
echo ""
echo "8️⃣ Validação final..."
ssh -i ~/.ssh/id_rsa "$HOMELAB_USER@$HOMELAB_HOST" << 'FINAL_CHECK'
echo "Service status:"
sudo systemctl status eddie-central-extended-metrics.service --no-pager | grep -E "Active|PID" || true

echo ""
echo "Port 9106 listening:"
sudo ss -ltnp | grep 9106 || echo "⚠️  Porta 9106 não respondendo"

echo ""
echo "Sample metrics:"
curl -s http://localhost:9106/metrics | grep -E "^conversation_count_total|^active_conversations|^agent_memory" | head -5

echo ""
echo "Prometheus job status:"
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import sys, json
data = json.load(sys.stdin)
for job in data.get('data', {}).get('activeTargets', []):
    if 'eddie-central-extended' in job.get('labels', {}).get('job', ''):
        print(f\"  Job: {job['labels']['job']}\")
        print(f\"  Health: {job['health']}\")
        print(f\"  Target: {job['scrapeUrl']}\")
" || echo "⚠️  Job não presente ainda (pode levar até 1min)"
FINAL_CHECK

# =========================================================================
# CONCLUSÃO
# =========================================================================
echo ""
echo "========================================"
echo "✅ DEPLOY FASE 2 CONCLUÍDO"
echo "========================================"
echo ""
echo "🔍 Próximos passos:"
echo "  1. Aguardar 60s para Prometheus scrape as métricas"
echo "  2. Executar: python3 validate_eddie_central_api.py"
echo "  3. Verificar dashboard em https://grafana.rpa4all.com/d/eddie-central/"
echo ""
echo "📊 Métricas implementadas (porta 9106):"
echo "  ✅ conversation_count_total"
echo "  ✅ active_conversations_total"
echo "  ✅ agent_memory_decisions_total"
echo "  ✅ ipc_pending_requests"
echo "  ✅ agent_confidence_score"
echo "  ✅ agent_feedback_score"
echo ""
echo "🔧 Para debug:"
echo "  ssh homelab@192.168.15.2 'sudo journalctl -u eddie-central-extended-metrics -f'"
echo "  ssh homelab@192.168.15.2 'curl http://localhost:9106/metrics'"
echo ""
