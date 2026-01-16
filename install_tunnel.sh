#!/bin/bash
# Instalar e configurar Cloudflare Tunnel para expor LLMs
# Executar como: bash install_tunnel.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     EXPOSIÇÃO DE LLMs PELA INTERNET - CLOUDFLARE TUNNEL    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Verificar se já está instalado
if command -v cloudflared &> /dev/null; then
    echo "✅ Cloudflared já está instalado: $(cloudflared --version)"
else
    echo "📦 Instalando Cloudflare Tunnel..."
    
    # Detectar arquitetura
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
    elif [ "$ARCH" = "aarch64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb"
    else
        echo "❌ Arquitetura não suportada: $ARCH"
        exit 1
    fi
    
    cd /tmp
    curl -L --output cloudflared.deb "$CLOUDFLARED_URL"
    sudo dpkg -i cloudflared.deb
    rm cloudflared.deb
    
    echo "✅ Instalado: $(cloudflared --version)"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    SERVIÇOS DISPONÍVEIS                    ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  1. Ollama API      - localhost:11434                      ║"
echo "║  2. RAG API         - localhost:8001                       ║"
echo "║  3. GitHub Agent    - localhost:8502                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Criar serviço systemd para o tunnel
echo "📝 Criando serviço systemd para tunnel permanente..."

sudo tee /etc/systemd/system/cloudflare-ollama.service > /dev/null << 'EOF'
[Unit]
Description=Cloudflare Tunnel for Ollama LLM
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=homelab
ExecStart=/usr/bin/cloudflared tunnel --url http://localhost:11434 --no-autoupdate
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/cloudflare-ollama.log
StandardError=append:/var/log/cloudflare-ollama.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Serviço criado!"
echo ""

# Perguntar se quer iniciar agora
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    COMO USAR                               ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║                                                            ║"
echo "║  🚀 INICIAR TUNNEL (gera URL pública):                     ║"
echo "║     sudo systemctl start cloudflare-ollama                 ║"
echo "║                                                            ║"
echo "║  📋 VER URL GERADA:                                        ║"
echo "║     sudo journalctl -u cloudflare-ollama -f                ║"
echo "║     (procure por 'https://...trycloudflare.com')           ║"
echo "║                                                            ║"
echo "║  🔄 HABILITAR NO BOOT:                                     ║"
echo "║     sudo systemctl enable cloudflare-ollama                ║"
echo "║                                                            ║"
echo "║  ⏹️  PARAR TUNNEL:                                         ║"
echo "║     sudo systemctl stop cloudflare-ollama                  ║"
echo "║                                                            ║"
echo "║  🖥️  TUNNEL MANUAL (teste rápido):                         ║"
echo "║     cloudflared tunnel --url http://localhost:11434        ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Iniciar o serviço
echo "🚀 Iniciando tunnel..."
sudo systemctl daemon-reload
sudo systemctl start cloudflare-ollama

sleep 3

echo ""
echo "📋 Buscando URL pública..."
echo ""

# Mostrar logs para ver a URL
sudo journalctl -u cloudflare-ollama --no-pager -n 20 | grep -E "https://.*trycloudflare.com|INF" | tail -10

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "💡 Para ver a URL completa, execute:"
echo "   sudo journalctl -u cloudflare-ollama -f"
echo ""
echo "🔗 A URL terá formato: https://NOME-ALEATORIO.trycloudflare.com"
echo "   Use esta URL para acessar seu Ollama de qualquer lugar!"
echo ""
echo "📝 Exemplo de uso remoto:"
echo "   curl https://SUA-URL.trycloudflare.com/api/tags"
echo "═══════════════════════════════════════════════════════════════"
