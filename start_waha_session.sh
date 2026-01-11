#!/bin/bash
# Script para iniciar sessão WAHA

curl -s -X POST "http://localhost:3000/api/sessions/start" \
  -H "X-Api-Key: secret123" \
  -H "Content-Type: application/json" \
  -d '{"name":"default"}' | python3 -m json.tool
