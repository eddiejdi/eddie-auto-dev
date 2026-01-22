#!/bin/bash
# deploy.sh - Deploy do túnel no Fly.io

set -e

# If the environment variable FLY_MINIMAL=1 or the script is called with --fly-minimal,
# the script will set the deployed Fly app to `shared-cpu-1x` and scale to 1 instance.
FLY_MINIMAL=0
for a in "$@"; do
    if [ "$a" = "--fly-minimal" ]; then
        FLY_MINIMAL=1
    fi
done

if [ "${FLY_MINIMAL_ENV:-0}" = "1" ]; then
    FLY_MINIMAL=1
fi

cd "$(dirname "$0")/.."

echo "🚀 Deploying Homelab Tunnel to Fly.io"
echo ""

# Verificar se o app já existe
if fly status &> /dev/null; then
    echo "📦 App já existe, atualizando..."
        fly deploy
        if [ "$FLY_MINIMAL" = "1" ]; then
            echo "Applying minimal VM size and instance count (shared-cpu-1x, count 1)"
            fly scale vm shared-cpu-1x --app homelab-tunnel || true
            fly scale count 1 --app homelab-tunnel || true
        fi
else
    echo "🆕 Criando novo app..."
    fly launch --name homelab-tunnel --region gru --no-deploy
    
    # Configurar secrets se necessário
    echo ""
    echo "Configurando variáveis de ambiente..."
    fly secrets set HOMELAB_HOST=192.168.15.2 2>/dev/null || true
    
        fly deploy
        if [ "$FLY_MINIMAL" = "1" ]; then
            echo "Applying minimal VM size and instance count (shared-cpu-1x, count 1)"
            fly scale vm shared-cpu-1x --app homelab-tunnel || true
            fly scale count 1 --app homelab-tunnel || true
        fi
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
