#!/bin/bash
# Script para testar instrumentação Prometheus do Homelab Advisor

set -e

ADVISOR_URL="${1:-http://localhost:8085}"
METRICS_URL="${ADVISOR_URL}/metrics"

echo "📊 Testando instrumentação Prometheus do Homelab Advisor"
echo "   URL: $ADVISOR_URL"
echo "   Metrics: $METRICS_URL"
echo ""

# Função para fazer requisições de teste
test_endpoint() {
    local endpoint=$1
    local method=${2:-GET}
    echo "🧪 Testando $method $endpoint..."
    if [ "$method" = "GET" ]; then
        curl -sS "$ADVISOR_URL$endpoint" > /dev/null 2>&1 || true
    else
        curl -sS -X "$method" "$ADVISOR_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d '{"scope":"performance"}' > /dev/null 2>&1 || true
    fi
}

# Fazer algumas requisições para gerar métricas
echo "⏳ Gerando dados para Prometheus..."
test_endpoint "/health"
test_endpoint "/analyze" "POST"
sleep 2

# Buscar e verificar métricas
echo ""
echo "📈 Métricas disponíveis:"
echo ""

# HTTP Requests
echo "✅ HTTP Requests:"
curl -sS "$METRICS_URL" | grep "^http_requests_total{" | head -3 || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
echo "✅ HTTP Request Duration:"
curl -sS "$METRICS_URL" | grep "^http_request_duration_seconds_" | head -3 || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
echo "✅ Advisor Analysis:"
curl -sS "$METRICS_URL" | grep "^advisor_analysis_total" || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
echo "✅ Advisor IPC Pending:"
curl -sS "$METRICS_URL" | grep "^advisor_ipc_pending_requests" || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
echo "✅ Advisor LLM Calls:"
curl -sS "$METRICS_URL" | grep "^advisor_llm_calls_total" || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
echo "✅ Advisor LLM Duration:"
curl -sS "$METRICS_URL" | grep "^advisor_llm_duration_seconds_" | head -3 || echo "   ⚠️  Nenhuma métrica encontrada"

echo ""
# Heartbeat metric
echo "✅ Advisor Heartbeat metric:"
curl -sS "$METRICS_URL" | grep "^advisor_heartbeat_timestamp" || echo "   ⚠️  advisor_heartbeat_timestamp ausente"

echo ""
echo "📊 Todas as métricas (contagem):"
TOTAL=$(curl -sS "$METRICS_URL" | grep -v "^#" | grep -v "^$" | wc -l)
echo "   Total de linhas de métricas: $TOTAL"

echo ""
echo "✅ Teste completo! Dashboard disponível em Grafana"
echo ""
