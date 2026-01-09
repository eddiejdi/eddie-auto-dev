#!/bin/bash
# Teste completo do fluxo GitHub Agent

echo "=== Teste 1: Parse de Intent ==="
curl -s -X POST "http://192.168.15.2:11434/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"github-agent:latest",
    "messages":[
      {"role":"system","content":"Você é um assistente de GitHub. Retorne APENAS JSON: {\"action\": \"list_issues\", \"params\": {\"owner\": \"microsoft\", \"repo\": \"vscode\"}, \"confidence\": 1.0}"},
      {"role":"user","content":"issues do microsoft/vscode"}
    ],
    "temperature":0.1
  }'

echo ""
echo ""
echo "=== Teste 2: API GitHub direta ==="
curl -s "https://api.github.com/repos/microsoft/vscode/issues?state=open&per_page=1" | head -c 500
