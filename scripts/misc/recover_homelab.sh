#!/bin/bash
# Script de recuperação automática do homelab
# Tenta diferentes métodos para restaurar conectividade

echo "🔧 RECUPERAÇÃO AUTOMÁTICA - HOMELAB"
echo "===================================="

# Método 1: Ping simples
echo "1. Testando conectividade básica..."
if ping -c 3 -W 2 192.168.15.2 >/dev/null 2>&1; then
    echo "✅ Ping OK - Servidor respondendo"
else
    echo "❌ Ping falhou - Servidor pode estar offline"
fi

# Método 2: Wake-on-LAN
echo ""
echo "2. Tentando Wake-on-LAN..."
if command -v etherwake >/dev/null 2>&1; then
    etherwake d0:94:66:bb:c4:f6
    echo "📡 Pacote WoL enviado (MAC: d0:94:66:bb:c4:f6)"
    echo "⏳ Aguardando 30 segundos para boot..."
    sleep 30

    if ping -c 3 -W 2 192.168.15.2 >/dev/null 2>&1; then
        echo "✅ Wake-on-LAN bem-sucedido!"
    else
        echo "❌ Wake-on-LAN falhou"
    fi
else
    echo "⚠️ etherwake não instalado - pulando WoL"
fi

# Método 3: Verificar SSH
echo ""
echo "3. Testando SSH..."
if ssh -o ConnectTimeout=10 -o BatchMode=yes homelab@192.168.15.2 "echo 'SSH OK'" >/dev/null 2>&1; then
    echo "✅ SSH OK - Conectividade restaurada"

    # Verificar serviços
    echo ""
    echo "4. Verificando serviços..."
    services=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "ps aux | grep -E '(waha|ollama|docker)' | grep -v grep | wc -l" 2>/dev/null)
    echo "📊 Serviços rodando: $services"

    # Verificar WAHA
    waha_status=$(ssh -o ConnectTimeout=5 homelab@192.168.15.2 "curl -s -H 'X-Api-Key: 757fae2686eb44479b9a34f1b62dbaf3' 'http://localhost:3001/api/sessions' | jq -r '.status // .[0].status' 2>/dev/null" 2>/dev/null)
    if [ "$waha_status" = "WORKING" ]; then
        echo "✅ WAHA: WORKING"
        echo ""
        echo "🎉 SISTEMA PRONTO PARA PROCESSAMENTO!"
        echo "Execute: ./safe_process.sh --process-one-by-one"
        exit 0
    else
        echo "❌ WAHA: $waha_status (precisa reconectar WhatsApp)"
        echo ""
        echo "📱 Para reconectar WhatsApp:"
        echo "ssh homelab@192.168.15.2"
        echo "curl -X POST -H 'X-Api-Key: 757fae2686eb44479b9a34f1b62dbaf3' 'http://localhost:3001/api/default/auth/qr' > /tmp/whatsapp_qr.txt"
        echo "cat /tmp/whatsapp_qr.txt"
        echo "# Escaneie o QR no WhatsApp"
    fi

else
    echo "❌ SSH ainda falhando"
    echo ""
    echo "🔍 POSSÍVEIS CAUSAS:"
    echo "   - Servidor fisicamente desligado"
    echo "   - Problema de rede/rede elétrica"
    echo "   - Firewall bloqueando conexões"
    echo "   - Servidor travado (kernel panic)"
    echo ""
    echo "💡 PRÓXIMOS PASSOS:"
    echo "   1. Verifique se o servidor está ligado fisicamente"
    echo "   2. Teste conectividade de outros dispositivos na rede"
    echo "   3. Se possível, acesse via console físico"
    echo "   4. Verifique logs do router/modem"
fi

echo ""
echo "⏰ Status final: RECUPERAÇÃO CONCLUÍDA"
exit 1