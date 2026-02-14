#!/bin/bash
# Script de verificação de saúde do servidor homelab
# Executar antes do processamento para evitar sobrecarga

echo "🔍 VERIFICAÇÃO DE SAÚDE - HOMELAB"
echo "=================================="

# Verificar conectividade SSH
echo -n "SSH connectivity: "
if ssh -o ConnectTimeout=5 -o BatchMode=yes homelab@192.168.15.2 "echo 'OK'" >/dev/null 2>&1; then
    echo "✅ OK"
else
    echo "❌ FAIL - Servidor inacessível"
    exit 1
fi

# Verificar serviços críticos
echo -n "Serviços críticos: "
services=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "ps aux | grep -E '(waha|ollama|docker)' | grep -v grep | wc -l" 2>/dev/null)
if [ "$services" -ge 2 ]; then
    echo "✅ OK ($services serviços rodando)"
else
    echo "❌ FAIL - Serviços críticos não encontrados"
    exit 1
fi

# Verificar uso de memória
echo -n "Uso de memória: "
mem_usage=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "free | grep Mem | awk '{print int(\$3/\$2 * 100.0)}'" 2>/dev/null)
if [ "$mem_usage" -lt 90 ]; then
    echo "✅ OK (${mem_usage}%)"
else
    echo "❌ FAIL - Memória alta (${mem_usage}%)"
    exit 1
fi

# Verificar uso de CPU
echo -n "Uso de CPU: "
cpu_usage=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\([0-9.]*\)%* id.*/\1/' | awk '{print 100 - \$1}'" 2>/dev/null)
if [ "$(echo "$cpu_usage < 80" | bc -l)" -eq 1 ]; then
    echo "✅ OK (${cpu_usage}%)"
else
    echo "❌ FAIL - CPU alta (${cpu_usage}%)"
    exit 1
fi

# Verificar espaço em disco
echo -n "Espaço em disco: "
disk_usage=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "df / | tail -1 | awk '{print \$5}' | sed 's/%//'" 2>/dev/null)
if [ "$disk_usage" -lt 90 ]; then
    echo "✅ OK (${disk_usage}%)"
else
    echo "❌ FAIL - Disco cheio (${disk_usage}%)"
    exit 1
fi

# Verificar status WAHA
echo -n "WAHA API: "
if ssh -o ConnectTimeout=5 homelab@192.168.15.2 "curl -s -H 'X-Api-Key: 757fae2686eb44479b9a34f1b62dbaf3' 'http://localhost:3001/api/sessions' | jq -r '.status // .[0].status' 2>/dev/null" | grep -q "WORKING"; then
    echo "✅ OK (WORKING)"
else
    echo "❌ FAIL - WAHA não está WORKING"
    exit 1
fi

echo ""
echo "🎉 TODAS AS VERIFICAÇÕES PASSARAM!"
echo "✅ Servidor pronto para processamento"
echo ""
echo "💡 Recomendações para processamento seguro:"
echo "   - Use --process-one-by-one para processamento gradual"
echo "   - Máximo 5 mensagens por execução"
echo "   - Monitore logs em tempo real"
echo "   - Pare imediatamente se notar lentidão"