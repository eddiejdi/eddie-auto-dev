#!/bin/bash
# Test API endpoints

echo "=== Testing Code Generation ==="
curl -s --max-time 120 -X POST http://192.168.15.2:8503/code/generate \
  -H "Content-Type: application/json" \
  -d '{"language":"python","description":"soma de dois numeros","context":""}' | head -100

echo ""
echo "=== Checking Communication Messages ==="
curl -s http://192.168.15.2:8503/communication/messages?limit=10 | python3 -m json.tool
