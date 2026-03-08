#!/bin/bash
# Deploy Agent Neural Network Dashboard to Grafana
# Configura exporter de métricas e instala dashboard

set -e

echo "=================================================================="
echo "DEPLOY: AGENT NEURAL NETWORK DASHBOARD"
echo "=================================================================="

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-Shared@2026}"

echo ""
echo "📦 Passo 1: Copiando arquivos para o servidor..."
scp specialized_agents/agent_network_exporter.py ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/specialized_agents/
scp systemd/agent-network-exporter.service ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/systemd/
scp grafana/dashboards/agent-neural-network.json ${SSH_USER}@${SSH_HOST}:~/shared-auto-dev/grafana/dashboards/

echo ""
echo "🔧 Passo 2: Instalando service systemd no servidor..."
ssh ${SSH_USER}@${SSH_HOST} "sudo cp ~/shared-auto-dev/systemd/agent-network-exporter.service /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable agent-network-exporter && \
    sudo systemctl restart agent-network-exporter"

echo ""
echo "⏳ Aguardando exporter inicializar..."
sleep 5

echo ""
echo "✅ Passo 3: Verificando status do exporter..."
ssh ${SSH_USER}@${SSH_HOST} "sudo systemctl status agent-network-exporter --no-pager | head -20"

echo ""
echo "📊 Passo 4: Testando endpoint de métricas..."
ssh ${SSH_USER}@${SSH_HOST} "curl -s http://localhost:9101/metrics | head -20"

echo ""
echo "📈 Passo 5: Configurando datasource Prometheus no Grafana (se necessário)..."
ssh ${SSH_USER}@${SSH_HOST} "curl -s -X POST \
    -H 'Content-Type: application/json' \
    -d '{
      \"name\": \"Agent Metrics\",
      \"type\": \"prometheus\",
      \"url\": \"http://localhost:9090\",
      \"access\": \"proxy\",
      \"isDefault\": false
    }' \
    http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/datasources 2>&1 | grep -v 'data source with the same name already exists' || echo 'Datasource já existe ou criado'"

echo ""
echo "📈 Passo 6: Configurando datasource PostgreSQL no Grafana (se necessário)..."
ssh ${SSH_USER}@${SSH_HOST} "curl -s -X POST \
    -H 'Content-Type: application/json' \
    -d '{
      \"name\": \"PostgreSQL\",
      \"type\": \"postgres\",
      \"url\": \"localhost:5432\",
      \"database\": \"postgres\",
      \"user\": \"postgres\",
      \"secureJsonData\": {
        \"password\": \"shared_memory_2026\"
      },
      \"jsonData\": {
        \"sslmode\": \"disable\",
        \"postgresVersion\": 1500
      },
      \"access\": \"proxy\",
      \"isDefault\": false
    }' \
    http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/datasources 2>&1 | grep -v 'data source with the same name already exists' || echo 'Datasource já existe ou criado'"

echo ""
echo "🎨 Passo 7: Importando dashboard no Grafana..."
ssh ${SSH_USER}@${SSH_HOST} "curl -s -X POST \
    -H 'Content-Type: application/json' \
    -d @/home/homelab/shared-auto-dev/grafana/dashboards/agent-neural-network.json \
    http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/dashboards/db"

echo ""
echo "=================================================================="
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "=================================================================="
echo ""
echo "📊 Dashboard disponível em:"
echo "   ${GRAFANA_URL}/d/agent-neural-network/agent-neural-network"
echo ""
echo "📈 Métricas disponíveis em:"
echo "   http://${SSH_HOST}:9101/metrics"
echo ""
echo "🔍 Para verificar logs:"
echo "   ssh ${SSH_USER}@${SSH_HOST} 'sudo journalctl -u agent-network-exporter -f'"
echo ""
echo "=================================================================="
