#!/bin/bash
# setup-flyio.sh - Configuração inicial do Fly.io

set -e

echo "🚀 Configurando Fly.io Tunnel"
echo ""

# Verificar se flyctl está instalado
if ! command -v fly &> /dev/null; then
    echo "📦 Instalando Fly CLI..."
    curl -L https://fly.io/install.sh | sh
    export FLYCTL_INSTALL="$HOME/.fly"
    export PATH="$FLYCTL_INSTALL/bin:$PATH"
    
    # Adicionar ao bashrc
    echo 'export FLYCTL_INSTALL="$HOME/.fly"' >> ~/.bashrc
    echo 'export PATH="$FLYCTL_INSTALL/bin:$PATH"' >> ~/.bashrc
fi

# Verificar autenticação
echo ""
echo "🔐 Verificando autenticação..."
if ! fly auth whoami &> /dev/null; then
    echo "Por favor, faça login no Fly.io:"
    fly auth login
fi

echo ""
echo "✅ Fly CLI instalado e autenticado!"
echo ""
echo "Próximos passos:"
echo "1. cd /home/homelab/projects/flyio-tunnel"
echo "2. fly launch --name homelab-tunnel --region gru --no-deploy"
echo "3. fly deploy"
echo ""
echo "Ou execute: ./scripts/deploy.sh"
