#!/bin/bash
# deploy.sh - Deploy do túnel no Fly.io

set -e

cd "$(dirname "$0")/.."

echo "🚀 Deploying Homelab Tunnel to Fly.io"
echo ""

# Verificar se o app já existe
if fly status &> /dev/null; then
    echo "📦 App já existe, atualizando..."
    fly deploy
else
    echo "🆕 Criando novo app..."
    fly launch --name homelab-tunnel --region gru --no-deploy
    
    # Configurar secrets se necessário
    echo ""
    echo "Configurando variáveis de ambiente..."
    fly secrets set HOMELAB_HOST=192.168.15.2 2>/dev/null || true
    
    fly deploy
fi

echo ""
echo "✅ Deploy concluído!"
echo ""
fly status

echo ""
echo "🌐 URLs disponíveis:"
echo "- https://homelab-tunnel.fly.dev/"
echo "- https://homelab-tunnel.fly.dev/api/ollama"
echo "- https://homelab-tunnel.fly.dev/v1/chat/completions"
