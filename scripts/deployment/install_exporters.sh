#!/bin/bash
# Script para instalar Node Exporter e cAdvisor no servidor

set -e

echo "🔧 Instalando Exporters para Dashboard Neural"
echo "=============================================="
echo

HOMELAB_HOST="${HOMELAB_HOST:-localhost}"
HOMELAB_SSH="${HOMELAB_SSH:-homelab@${HOMELAB_HOST}}"

# Copiar arquivos
echo "📤 Copiando arquivos de configuração..."
scp docker-compose-exporters.yml $HOMELAB_SSH:/tmp/
scp prometheus-config.yml $HOMELAB_SSH:/tmp/

# Executar no servidor
ssh $HOMELAB_SSH << 'REMOTE_COMMANDS'
set -e

echo "🚀 Iniciando instalação no servidor..."
echo

# 1. Iniciar Node Exporter e cAdvisor
echo "1️⃣ Iniciando Node Exporter e cAdvisor..."
cd /tmp
docker-compose -f docker-compose-exporters.yml up -d

echo "   ✅ Node Exporter: http://localhost:9100/metrics"
echo "   ✅ cAdvisor: http://localhost:8080/metrics"
echo

# 2. Aguardar exporters ficarem prontos
echo "2️⃣ Aguardando exporters ficarem prontos..."
sleep 5

# 3. Verificar se estão rodando
echo "3️⃣ Verificando containers..."
docker ps | grep -E '(node-exporter|cadvisor)' || echo "⚠️ Containers não encontrados"
echo

# 4. Atualizar configuração do Prometheus
echo "4️⃣ Atualizando configuração do Prometheus..."

# Verificar onde está o prometheus
PROM_CONFIG=$(docker inspect prometheus 2>/dev/null | grep -o '"/etc/prometheus":"[^"]*"' | cut -d':' -f2 | tr -d '"' | head -1)

if [ -z "$PROM_CONFIG" ]; then
    echo "⚠️ Não foi possível localizar configuração do Prometheus"
    echo "   Tentando localização padrão..."
    PROM_CONFIG="/var/lib/docker/volumes/prometheus-config/_data"
fi

echo "   Config dir: $PROM_CONFIG"

# Backup da configuração antiga
if [ -f "$PROM_CONFIG/prometheus.yml" ]; then
    sudo cp "$PROM_CONFIG/prometheus.yml" "$PROM_CONFIG/prometheus.yml.bak.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
fi

# Copiar nova configuração
sudo cp /tmp/prometheus-config.yml "$PROM_CONFIG/prometheus.yml" 2>/dev/null || \
    cp /tmp/prometheus-config.yml "$PROM_CONFIG/prometheus.yml"

echo "   ✅ Configuração atualizada"
echo

# 5. Recarregar Prometheus
echo "5️⃣ Recarregando Prometheus..."
docker exec prometheus kill -HUP 1 2>/dev/null || docker restart prometheus

echo "   ✅ Prometheus recarregado"
echo

# 6. Verificar targets
echo "6️⃣ Verificando novos targets (aguarde 15s)..."
sleep 15

curl -s http://localhost:9090/api/v1/targets 2>/dev/null | python3 << 'EOF'
import sys, json
try:
    data = json.load(sys.stdin)
    targets = data.get('data', {}).get('activeTargets', [])
    print(f"\n   Targets ativos: {len(targets)}")
    for t in targets:
        job = t.get('labels', {}).get('job', 'unknown')
        health = t.get('health', 'unknown')
        icon = '✅' if health == 'up' else '❌'
        print(f"   {icon} {job}: {health}")
except:
    print("   ⚠️ Não foi possível verificar targets")
EOF

echo
echo "✅ Instalação concluída!"
echo
echo "📊 Verificar dashboard em:"
echo "   http://localhost:3002/grafana/d/neural-network-v1/"
echo
echo "🔍 Testar métricas:"
echo "   curl http://localhost:9100/metrics | head"
echo "   curl http://localhost:8080/metrics | head"

REMOTE_COMMANDS

echo
echo "✨ Processo concluído!"
echo
echo "📝 Próximos passos:"
echo "  1. Abrir Grafana: ./open_grafana.sh"
echo "  2. Acessar dashboard neural: http://localhost:3002/grafana/d/neural-network-v1/"
echo "  3. Aguardar ~1 minuto para métricas aparecerem"
