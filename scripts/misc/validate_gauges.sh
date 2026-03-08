#!/bin/bash
# Validação de gauges do dashboard Grafana Eddie_whatsapp
# Verifica as métricas via Prometheus

set -euo pipefail

PROMETHEUS_URL="http://localhost:9090"
METRICS=(
  "shared_whatsapp_train_accuracy"
  "shared_whatsapp_val_accuracy"
  "shared_whatsapp_train_loss"
  "shared_whatsapp_val_loss"
  "shared_whatsapp_indexed_documents_total"
  "shared_whatsapp_inference_requests_total"
)

echo "=========================================================="
echo "🔍 VALIDADOR DE GAUGES - SHARED WHATSAPP"
echo "=========================================================="
echo ""

invalid_count=0
valid_count=0

for metric in "${METRICS[@]}"; do
  echo -n "📊 Validando $metric... "
  
  response=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=${metric}")
  status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))")
  
  if [ "$status" != "success" ]; then
    echo "❌ INVÁLIDO (Prometheus query failed)"
    invalid_count=$((invalid_count + 1))
    continue
  fi
  
  # Extrair valor
  result=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('data', {}).get('result', []):
    value = data['data']['result'][0].get('value', [None, None])[1]
    print(value)
else:
    print('null')
")
  
  if [ "$result" = "null" ] || [ -z "$result" ]; then
    echo "❌ INVÁLIDO (No value)"
    invalid_count=$((invalid_count + 1))
  elif echo "$result" | grep -qiE "(nan|undefined|^$)"; then
    echo "❌ INVÁLIDO (Invalid value: $result)"
    invalid_count=$((invalid_count + 1))
  else
    echo "✅ VÁLIDO (value: $result)"
    valid_count=$((valid_count + 1))
  fi
done

echo ""
echo "=========================================================="
echo "📈 RESULTADO FINAL"
echo "=========================================================="
echo "✅ Válidos: $valid_count"
echo "❌ Inválidos: $invalid_count"
echo ""

if [ $invalid_count -eq 0 ]; then
  echo "✅ TODOS OS GAUGES ESTÃO VÁLIDOS"
  exit 0
else
  echo "❌ $invalid_count gauge(s) com problema(s)"
  exit 1
fi
