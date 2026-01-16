#!/bin/bash
# Test BPM generate endpoint
curl -s -X POST 'http://localhost:8503/bpm/generate' \
  -H 'Content-Type: application/json' \
  -d '{"description": "processo de vendas simples", "name": "Vendas"}'
