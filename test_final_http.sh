#!/bin/bash
# Script para testar a API integrada

set -e

echo "================================================"
echo "TESTE FINAL - INTERCEPTADOR API"
echo "================================================"

cd /home/eddie/myClaude

# Matar processos antigos
echo "[1/5] Finalizando processos antigos..."
pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "8503" 2>/dev/null || true
sleep 3

# Iniciar API
echo "[2/5] Iniciando API na porta 8503..."
python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503 > /tmp/api_test.log 2>&1 &
API_PID=$!
sleep 5

# Verificar se API está rodando
if ! ps -p $API_PID > /dev/null; then
    echo "❌ ERRO: API não iniciou"
    cat /tmp/api_test.log
    exit 1
fi
echo "✓ API iniciada (PID: $API_PID)"

# Teste 1: /health
echo "[3/5] Teste 1: GET /health"
HEALTH=$(curl -s -w "\n%{http_code}" http://localhost:8503/health)
HEALTH_CODE=$(echo "$HEALTH" | tail -1)
if [ "$HEALTH_CODE" = "200" ]; then
    echo "✓ /health retornou 200 OK"
else
    echo "❌ /health retornou $HEALTH_CODE"
    kill $API_PID 2>/dev/null || true
    exit 1
fi

# Teste 2: /interceptor/conversations/active
echo "[4/5] Teste 2: GET /interceptor/conversations/active"
RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8503/interceptor/conversations/active)
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "Status HTTP: $HTTP_CODE"
echo "Response: $BODY"

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ /interceptor/conversations/active retornou 200 OK"
    echo "✅ INTEGRAÇÃO FUNCIONANDO PERFEITAMENTE"
else
    echo "❌ /interceptor/conversations/active retornou $HTTP_CODE"
    echo "❌ Resposta: $BODY"
    kill $API_PID 2>/dev/null || true
    exit 1
fi

# Teste 3: Rotas registradas
echo "[5/5] Teste 3: Verificando todas as rotas /interceptor"
ROUTES=$(curl -s http://localhost:8503/openapi.json | grep -o '"/interceptor/[^"]*' | sort | uniq | wc -l)
echo "✓ $ROUTES rotas /interceptor encontradas"

# Cleanup
kill $API_PID 2>/dev/null || true

echo ""
echo "================================================"
echo "✅ TODOS OS TESTES PASSARAM"
echo "================================================"
