#!/bin/bash
# Iniciar sessão WAHA com nova API key

curl -s -X POST "http://localhost:3000/api/sessions/start" \
  -H "X-Api-Key: 96263ae8a9804541849ebc5efa212e0e" \
  -H "Content-Type: application/json" \
  -d '{"name":"default"}' | python3 -m json.tool
