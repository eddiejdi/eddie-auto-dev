#!/bin/bash
# Validação em Produção

PROD_HOST="${PROD_HOST:-${HOMELAB_HOST:-localhost}}"
PROD_PORT="8503"

echo "================================================"
echo "VALIDAÇÃO - Produção"
echo "================================================"
echo "Host: $PROD_HOST:$PROD_PORT"
echo ""

# 1. Health check
echo "[1/6] Health Check..."
HEALTH=$(curl -s http://$PROD_HOST:$PROD_PORT/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ API respondendo"
else
    echo "✗ API não respondendo"
    exit 1
fi

# 2. Interceptador
echo ""
echo "[2/6] Interceptador de Conversas..."
INTERCEPTOR=$(curl -s http://$PROD_HOST:$PROD_PORT/interceptor/conversations/active)
if echo "$INTERCEPTOR" | grep -q "success"; then
    echo "✓ Interceptador funcional"
else
    echo "✗ Interceptador com erro"
    exit 1
fi

# 3. Dashboard Distribuído
echo ""
echo "[3/6] Dashboard Distribuído..."
DASHBOARD=$(curl -s http://$PROD_HOST:$PROD_PORT/distributed/precision-dashboard)
if echo "$DASHBOARD" | grep -q "agents"; then
    echo "✓ Dashboard funcional"
else
    echo "✗ Dashboard com erro"
    exit 1
fi

# 4. Testar roteamento
echo ""
echo "[4/6] Teste de Roteamento..."
ROUTE=$(curl -s -X POST "http://$PROD_HOST:$PROD_PORT/distributed/route-task?language=python" \
  -H "Content-Type: application/json" \
  -d '{"task":"teste","type":"code"}')
if echo "$ROUTE" | grep -q "success"; then
    echo "✓ Roteamento funcional"
else
    echo "✗ Roteamento com erro"
    exit 1
fi

# 5. Verificar rotas
echo ""
echo "[5/6] Verificando rotas registradas..."
ROUTES=$(curl -s http://$PROD_HOST:$PROD_PORT/openapi.json | grep -o '"/interceptor\|/distributed' | sort | uniq | wc -l)
echo "✓ $ROUTES rotas encontradas"

# 6. Performance
echo ""
echo "[6/6] Teste de Performance..."
START=$(date +%s%N)
curl -s http://$PROD_HOST:$PROD_PORT/health > /dev/null
END=$(date +%s%N)
TIME=$(( (END - START) / 1000000 ))
if [ $TIME -lt 100 ]; then
    echo "✓ Performance: ${TIME}ms (excelente)"
else
    echo "⚠ Performance: ${TIME}ms"
fi

echo ""
echo "================================================"
echo "✅ VALIDAÇÃO EM PROD - SUCESSO"
echo "================================================"
echo ""
echo "Endpoints ativos:"
echo "  - Health: http://$PROD_HOST:$PROD_PORT/health"
echo "  - Interceptador: http://$PROD_HOST:$PROD_PORT/interceptor/conversations/active"
echo "  - Dashboard: http://$PROD_HOST:$PROD_PORT/distributed/precision-dashboard"
echo ""
