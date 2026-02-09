#!/bin/bash

# Setup Grafana Dashboard para Review System
# Adiciona datasource e importa dashboard JSON

set -e

GRAFANA_HOST="${GRAFANA_HOST:-localhost}"
GRAFANA_PORT="${GRAFANA_PORT:-3002}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
PROMETHEUS_HOST="${PROMETHEUS_HOST:-192.168.15.2}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"

BASE_URL="http://${GRAFANA_HOST}:${GRAFANA_PORT}"
AUTH="${GRAFANA_USER}:${GRAFANA_PASSWORD}"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 Setup: Grafana Dashboard para Review System"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Grafana: ${BASE_URL}"
echo "Prometheus: http://${PROMETHEUS_HOST}:${PROMETHEUS_PORT}"

# 1. Testar conexão com Grafana
echo "[1/3] Testando conexão com Grafana..."
if ! curl -s -m 5 "${BASE_URL}/health" | grep -q "ok"; then
    echo "❌ Grafana não respondeu em ${BASE_URL}"
    echo "   Verifique: docker ps | grep grafana"
    exit 1
fi
echo "✅ Grafana respondendo"

# 2. Criar/verificar datasource Prometheus
echo "[2/3] Criando datasource Prometheus..."
DS_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/datasources" \
  -H "Content-Type: application/json" \
  -u "${AUTH}" \
  --data-raw "{
    \"name\": \"Prometheus\",
    \"type\": \"prometheus\",
    \"url\": \"http://${PROMETHEUS_HOST}:${PROMETHEUS_PORT}\",
    \"access\": \"proxy\",
    \"isDefault\": true,
    \"jsonData\": {}
  }" 2>&1)

# Verificar se datasource já existe ou foi criado
if echo "${DS_RESPONSE}" | grep -q '"id"'; then
    DS_ID=$(echo "${DS_RESPONSE}" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "✅ Datasource Prometheus criado/existe (ID: ${DS_ID})"
elif echo "${DS_RESPONSE}" | grep -q "already exists"; then
    echo "✅ Datasource Prometheus já existe"
else
    echo "⚠️  Resposta inesperada:"
    echo "${DS_RESPONSE}" | head -5
fi

# 3. Importar dashboard JSON
echo "[3/3] Importando dashboard JSON..."
DASHBOARD_FILE="$(cd "$(dirname "$0")" && pwd)/review-system.json"

if [ ! -f "${DASHBOARD_FILE}" ]; then
    echo "❌ Arquivo de dashboard não encontrado: ${DASHBOARD_FILE}"
    exit 1
fi

IMPORT_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "${AUTH}" \
  --data @- << EOF
{
  "dashboard": $(cat "${DASHBOARD_FILE}"),
  "overwrite": true
}
EOF
)

if echo "${IMPORT_RESPONSE}" | grep -q '"id"'; then
    DASH_ID=$(echo "${IMPORT_RESPONSE}" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "✅ Dashboard importado com sucesso (ID: ${DASH_ID})"
    echo "   URL: ${BASE_URL}/d/review-system-metrics/review-quality-gate-system"
else
    echo "❌ Erro ao importar dashboard:"
    echo "${IMPORT_RESPONSE}" | head -10
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ Setup concluído!"
echo ""
echo "Próximos passos:"
echo "  1. Acessar Grafana: ${BASE_URL}"
echo "  2. Dashboard: Review Quality Gate System"
echo "  3. Verificar métricas"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
