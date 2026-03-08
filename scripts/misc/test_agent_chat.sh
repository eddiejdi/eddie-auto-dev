#!/bin/bash
# Testes funcionais do Agent Chat

echo "=== TESTES FUNCIONAIS AGENT CHAT ==="
echo ""

# Teste 1: Streamlit rodando
echo "1. Teste: Agent Chat (Streamlit) rodando..."
if curl -s http://localhost:8505 | grep -q "Streamlit"; then
    echo "   ✅ PASS - Streamlit respondendo na porta 8505"
else
    echo "   ❌ FAIL - Streamlit não responde"
fi

# Teste 2: API de agentes
echo ""
echo "2. Teste: API de Agentes..."
AGENTS=$(curl -s http://localhost:8503/agents)
if echo "$AGENTS" | grep -q "python"; then
    echo "   ✅ PASS - API retorna linguagens disponíveis"
else
    echo "   ❌ FAIL - API não retorna linguagens"
fi

# Teste 3: Geração de código
echo ""
echo "3. Teste: Geração de código..."
GEN_RESULT=$(curl -s -X POST http://localhost:8503/code/generate \
    -H "Content-Type: application/json" \
    -d '{"description": "hello world function", "language": "python", "context": ""}')
if echo "$GEN_RESULT" | grep -q "code\|print\|def"; then
    echo "   ✅ PASS - Geração de código funcionando"
    echo "   Resultado: $(echo $GEN_RESULT | head -c 100)..."
else
    echo "   ❌ FAIL - Geração de código falhou"
    echo "   Resultado: $GEN_RESULT"
fi

# Teste 4: Execução de código
echo ""
echo "4. Teste: Execução de código..."
EXEC_RESULT=$(curl -s -X POST http://localhost:8503/code/execute \
    -H "Content-Type: application/json" \
    -d '{"code": "print(2+2)", "language": "python"}')
if echo "$EXEC_RESULT" | grep -q "4\|output"; then
    echo "   ✅ PASS - Execução de código funcionando"
    echo "   Output: $(echo $EXEC_RESULT | head -c 100)..."
else
    echo "   ❌ FAIL - Execução de código falhou"
    echo "   Resultado: $EXEC_RESULT"
fi

# Teste 5: Auto-scaler status
echo ""
echo "5. Teste: Auto-scaler..."
SCALER=$(curl -s http://localhost:8503/autoscaler/status)
if echo "$SCALER" | grep -q "current_agents"; then
    echo "   ✅ PASS - Auto-scaler respondendo"
else
    echo "   ❌ FAIL - Auto-scaler não responde"
fi

# Teste 6: Instructor status
echo ""
echo "6. Teste: Instructor Agent..."
INSTRUCTOR=$(curl -s http://localhost:8503/instructor/status)
if echo "$INSTRUCTOR" | grep -q "running"; then
    echo "   ✅ PASS - Instructor respondendo"
else
    echo "   ❌ FAIL - Instructor não responde"
fi

echo ""
echo "=== FIM DOS TESTES ==="
