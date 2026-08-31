#!/bin/bash
set -e

echo "════════════════════════════════════════════════════════════"
echo "  🔍 VALIDAÇÃO DE LIMITES DE CONTAINERS - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════"
echo

# Containers que devem ter limites
CONTAINERS=(
  "open-webui:2:1"          # name:cpus:memory_gb
  "eddie-postgres:1.5:1"
  "openwebui-postgres:1:0.5"
  "grafana:0.5:0.5"
  "node-exporter:0.5:0.25"
  "waha:0.25:0.125"
  "homeassistant:0.5:0.5"
  "cadvisor:1:0.5"
  "nextcloud-db:1.5:1"
  "nextcloud-redis:0.5:0.25"
  "nextcloud-app:2:2"
  "nextcloud-cron:0.5:0.5"
)

echo "🔎 Verificando limites de CPU e Memória..."
echo

OK=0
FAIL=0
WARNING=0

for container_spec in "${CONTAINERS[@]}"; do
  IFS=':' read -r name cpu mem <<< "$container_spec"
  
  # Verificar se container existe
  if ! docker ps -a --format="{{.Names}}" | grep -q "^${name}$"; then
    echo "⚠️  AVISO: Container '$name' não encontrado"
    ((WARNING++))
    continue
  fi
  
  # Ver CPU limit
  cpu_quota=$(docker inspect "$name" --format="{{.HostConfig.CpuQuota}}" 2>/dev/null || echo "0")
  cpu_period=$(docker inspect "$name" --format="{{.HostConfig.CpuPeriod}}" 2>/dev/null || echo "100000")
  
  if [ "$cpu_quota" -gt 0 ] && [ "$cpu_period" -gt 0 ]; then
    calculated_cpu=$(echo "scale=2; $cpu_quota / $cpu_period" | bc)
    echo "✅ $name: CPU=${calculated_cpu} (limite: $cpu CPUs)"
    ((OK++))
  else
    echo "❌ $name: SEM LIMITE DE CPU"
    ((FAIL++))
  fi
  
  # Ver Memory limit
  memory=$(docker inspect "$name" --format="{{.HostConfig.Memory}}" 2>/dev/null || echo "0")
  if [ "$memory" -gt 0 ]; then
    memory_mb=$((memory / 1048576))
    echo "   Memória=${memory_mb}MB (limite: $((${mem%.*} * 1024))MB)"
  else
    echo "   ❌ SEM LIMITE DE MEMÓRIA"
  fi
  echo
done

echo "════════════════════════════════════════════════════════════"
echo "📊 RESULTADOS:"
echo "   ✅ OK:       $OK"
echo "   ❌ FALHAS:   $FAIL"
echo "   ⚠️  AVISOS:  $WARNING"
echo "════════════════════════════════════════════════════════════"

if [ $FAIL -eq 0 ]; then
  echo "🎉 Todos os containers têm limites configurados!"
  exit 0
else
  echo "⚠️  Alguns containers não têm limites. Execute docker update para corrigir"
  exit 1
fi
