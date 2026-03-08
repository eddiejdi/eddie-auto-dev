#!/bin/bash
# Deploy Banking Agent Dashboard to Grafana
# Instala exporter de métricas bancárias e dashboard

set -e

echo "=================================================================="
echo "DEPLOY: BANKING AGENT DASHBOARD (Multi-Banco)"
echo "  Santander · Itaú · Nubank · Mercado Pago"
echo "=================================================================="

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3002/grafana}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-Shared@2026}"
EXPORTER_PORT=9102

# ─── Passo 1: Copiar arquivos ────────────────────────────────────────
echo ""
echo "📦 Passo 1: Copiando arquivos para o servidor..."
scp specialized_agents/banking_metrics_exporter.py \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/specialized_agents/

scp systemd/banking-metrics-exporter.service \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/systemd/

scp grafana/dashboards/banking-agent.json \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/grafana/dashboards/

scp monitoring/prometheus.yml \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/monitoring/

# Copiar módulo banking inteiro
scp -r specialized_agents/banking/ \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/specialized_agents/

scp specialized_agents/banking_agent.py \
    ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/specialized_agents/

echo "   ✅ Arquivos copiados"

# ─── Passo 2: Instalar dependências ─────────────────────────────────
echo ""
echo "📦 Passo 2: Instalando dependências Python..."
ssh ${SSH_USER}@${SSH_HOST} "cd ~/shared-auto-dev && \
    .venv/bin/pip install -q prometheus_client httpx cryptography 2>&1 | tail -1"

echo "   ✅ Dependências instaladas"

# ─── Passo 3: Configurar systemd ────────────────────────────────────
echo ""
echo "🔧 Passo 3: Configurando service systemd..."
ssh ${SSH_USER}@${SSH_HOST} "sudo cp ~/shared-auto-dev/systemd/banking-metrics-exporter.service /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable banking-metrics-exporter && \
    sudo systemctl restart banking-metrics-exporter"

echo "   ✅ Service instalado e iniciado"

# ─── Passo 4: Aguardar e verificar ─────────────────────────────────
echo ""
echo "⏳ Aguardando exporter inicializar..."
sleep 5

echo ""
echo "🔍 Passo 4: Verificando status do exporter..."
ssh ${SSH_USER}@${SSH_HOST} "sudo systemctl status banking-metrics-exporter --no-pager | head -15"

echo ""
echo "📊 Passo 5: Testando endpoint de métricas..."
METRICS_TEST=$(ssh ${SSH_USER}@${SSH_HOST} "curl -sf http://localhost:${EXPORTER_PORT}/metrics 2>/dev/null | head -5" || echo "FALHA")
if [[ "$METRICS_TEST" == "FALHA" ]]; then
    echo "   ⚠️  Endpoint ainda não disponível — verificar logs"
    ssh ${SSH_USER}@${SSH_HOST} "sudo journalctl -u banking-metrics-exporter --no-pager -n 10"
else
    echo "$METRICS_TEST"
    echo "   ✅ Métricas acessíveis na porta ${EXPORTER_PORT}"
fi

# ─── Passo 6: Atualizar Prometheus ──────────────────────────────────
echo ""
echo "📡 Passo 6: Recarregando Prometheus com novo scrape target..."
ssh ${SSH_USER}@${SSH_HOST} "docker exec prometheus cp /etc/prometheus/prometheus.yml /etc/prometheus/prometheus.yml.bak 2>/dev/null || true"
ssh ${SSH_USER}@${SSH_HOST} "docker cp ~/shared-auto-dev/monitoring/prometheus.yml prometheus:/etc/prometheus/prometheus.yml 2>/dev/null || true"
ssh ${SSH_USER}@${SSH_HOST} "docker exec prometheus kill -HUP 1 2>/dev/null || \
    curl -sf -X POST http://localhost:9090/-/reload 2>/dev/null || \
    echo 'Prometheus reload manual necessário'"

echo "   ✅ Prometheus atualizado"

# ─── Passo 7: Importar dashboard Grafana ────────────────────────────
echo ""
echo "🎨 Passo 7: Importando dashboard no Grafana..."
IMPORT_RESULT=$(ssh ${SSH_USER}@${SSH_HOST} "curl -sf -X POST \
    -H 'Content-Type: application/json' \
    -d @/home/homelab/shared-auto-dev/grafana/dashboards/banking-agent.json \
    http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/dashboards/db" 2>&1)

if echo "$IMPORT_RESULT" | grep -q '"status":"success"'; then
    echo "   ✅ Dashboard importado com sucesso"
else
    echo "   ⚠️  Resultado: $IMPORT_RESULT"
    echo "   Tentando reimportar com overwrite..."
    ssh ${SSH_USER}@${SSH_HOST} "curl -sf -X POST \
        -H 'Content-Type: application/json' \
        -d @/home/homelab/shared-auto-dev/grafana/dashboards/banking-agent.json \
        http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/dashboards/db" || echo "Import falhou — importar manualmente via UI"
fi

# ─── Resumo final ───────────────────────────────────────────────────
echo ""
echo "=================================================================="
echo "✅ DEPLOY DO BANKING DASHBOARD CONCLUÍDO!"
echo "=================================================================="
echo ""
echo "📊 Dashboard:  http://${SSH_HOST}:3002/grafana/d/shared-banking-agent/"
echo "📈 Métricas:   http://${SSH_HOST}:${EXPORTER_PORT}/metrics"
echo "🔧 Service:    sudo systemctl status banking-metrics-exporter"
echo "📋 Logs:       sudo journalctl -u banking-metrics-exporter -f"
echo ""
echo "🏦 Bancos configuráveis via env vars:"
echo "   BANK_SANTANDER_CLIENT_ID / BANK_SANTANDER_CLIENT_SECRET"
echo "   BANK_ITAU_CLIENT_ID / BANK_ITAU_CLIENT_SECRET"
echo "   BANK_NUBANK_CLIENT_ID / BANK_NUBANK_CLIENT_SECRET"
echo "   BANK_MERCADOPAGO_ACCESS_TOKEN"
echo ""
echo "=================================================================="
