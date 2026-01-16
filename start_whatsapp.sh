#!/bin/bash
#
# Script rápido para iniciar o WhatsApp Bot
# Uso: ./start_whatsapp.sh
#

set -e

cd "$(dirname "$0")"

echo "🚀 Iniciando WhatsApp Bot..."
echo ""

# Verificar se WAHA está rodando
if docker ps | grep -q waha; then
    echo "✅ WAHA já está rodando"
else
    echo "⚠️ WAHA não está rodando. Iniciando..."
    
    # Verificar se container existe
    if docker ps -a | grep -q waha; then
        docker start waha
    else
        echo "❌ Container WAHA não existe. Execute primeiro:"
        echo "   ./install_whatsapp_bot.sh"
        exit 1
    fi
    
    sleep 5
fi

# Verificar status do WAHA
echo ""
echo "📊 Status do WAHA:"
curl -s http://localhost:3000/api/sessions/eddie 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Aguardando WAHA..."

echo ""
echo "📱 Para conectar o WhatsApp, acesse:"
echo "   http://localhost:3000/api/sessions/eddie/auth/qr"
echo ""
echo "   Ou veja os logs: docker logs -f waha"
echo ""

# Carregar variáveis de ambiente
if [ -f .env.whatsapp ]; then
    echo "📝 Carregando configurações de .env.whatsapp"
    export $(cat .env.whatsapp | grep -v '^#' | xargs)
fi

# Configurações padrão
export WHATSAPP_NUMBER=${WHATSAPP_NUMBER:-5511981193899}
export WAHA_URL=${WAHA_URL:-http://localhost:3000}
export OLLAMA_HOST=${OLLAMA_HOST:-http://192.168.15.2:11434}
export OLLAMA_MODEL=${OLLAMA_MODEL:-eddie-coder}
export ADMIN_NUMBERS=${ADMIN_NUMBERS:-5511981193899}

echo "🤖 Iniciando bot Python..."
echo "   Número: $WHATSAPP_NUMBER"
echo "   WAHA: $WAHA_URL"
echo "   Ollama: $OLLAMA_HOST"
echo "   Modelo: $OLLAMA_MODEL"
echo ""
echo "═══════════════════════════════════════════════════"
echo ""

# Iniciar bot
python3 whatsapp_bot.py
