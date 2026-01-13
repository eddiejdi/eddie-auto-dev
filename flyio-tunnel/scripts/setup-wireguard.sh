#!/bin/bash
# setup-wireguard.sh - Configurar WireGuard tunnel entre Fly.io e Homelab

set -e

echo "🔒 Configurando WireGuard Tunnel para Fly.io"
echo ""

# Verificar se WireGuard está instalado
if ! command -v wg &> /dev/null; then
    echo "📦 Instalando WireGuard..."
    sudo apt update
    sudo apt install -y wireguard wireguard-tools
fi

# Criar peer no Fly.io
echo "🔑 Criando peer no Fly.io..."
fly wireguard create personal homelab-peer > /tmp/fly-wireguard.conf 2>&1 || {
    echo "Peer pode já existir, tentando listar..."
    fly wireguard list
}

# Configurar WireGuard localmente
if [ -f /tmp/fly-wireguard.conf ]; then
    echo "📝 Configurando WireGuard local..."
    sudo cp /tmp/fly-wireguard.conf /etc/wireguard/fly0.conf
    sudo chmod 600 /etc/wireguard/fly0.conf
fi

# Habilitar IP forwarding
echo "🔧 Habilitando IP forwarding..."
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

echo ""
echo "✅ WireGuard configurado!"
echo ""
echo "Para ativar o túnel:"
echo "  sudo wg-quick up fly0"
echo ""
echo "Para verificar status:"
echo "  sudo wg show"
echo ""
echo "Para desativar:"
echo "  sudo wg-quick down fly0"
