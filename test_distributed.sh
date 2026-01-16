#!/bin/bash
# Teste do sistema distribuído Copilot + Homelab Agents

echo "================================================"
echo "TESTE - SISTEMA DISTRIBUÍDO"
echo "================================================"
echo ""

cd /home/eddie/myClaude

# 1. Iniciar API
echo "[1/4] Iniciando API..."
python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503 > /tmp/test_dist.log 2>&1 &
API_PID=$!
sleep 5

# 2. Testar endpoint de precision dashboard
echo "[2/4] Testando dashboard de precisão..."
DASHBOARD=$(curl -s http://localhost:8503/distributed/precision-dashboard)
echo "$DASHBOARD" | python3 -m json.tool 2>/dev/null | head -30

# 3. Testar roteamento de tarefa
echo ""
echo "[3/4] Testando roteamento de tarefa (Python)..."
curl -s -X POST "http://localhost:8503/distributed/route-task?language=python" \
  -H "Content-Type: application/json" \
  -d '{"task":"criar funcao fibonacci","type":"code"}' | python3 -m json.tool 2>/dev/null

# 4. Cleanup
echo ""
echo "[4/4] Finalizando..."
kill $API_PID 2>/dev/null || true

echo ""
echo "================================================"
echo "✅ TESTE CONCLUÍDO"
echo "================================================"
