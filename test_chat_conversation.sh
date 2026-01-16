#!/bin/bash
# Teste de conversa no Agent Chat

echo "=============================================="
echo "   TESTE DE CONVERSA - AGENT CHAT"
echo "=============================================="
echo ""

echo "📝 Pergunta 1: Gerar função fatorial"
echo "---"
RESP1=$(curl -s --max-time 90 -X POST http://localhost:8503/code/generate \
    -H "Content-Type: application/json" \
    -d '{"description": "função que calcula fatorial com recursão", "language": "python", "context": ""}')

echo "Resposta do Agent:"
echo "$RESP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code','Erro'))"
echo ""

echo "📝 Pergunta 2: Gerar API REST simples"
echo "---"
RESP2=$(curl -s --max-time 90 -X POST http://localhost:8503/code/generate \
    -H "Content-Type: application/json" \
    -d '{"description": "API REST com FastAPI que retorna hello world", "language": "python", "context": ""}')

echo "Resposta do Agent:"
echo "$RESP2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code','Erro'))"
echo ""

echo "📝 Pergunta 3: Executar código simples"
echo "---"
RESP3=$(curl -s --max-time 30 -X POST http://localhost:8503/code/execute \
    -H "Content-Type: application/json" \
    -d '{"code": "for i in range(5): print(f\"Contagem: {i}\")", "language": "python"}')

echo "Resultado da execução:"
echo "$RESP3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('output', d.get('error','Erro')))"
echo ""

echo "=============================================="
echo "   TESTE DE CONVERSA CONCLUÍDO"
echo "=============================================="
