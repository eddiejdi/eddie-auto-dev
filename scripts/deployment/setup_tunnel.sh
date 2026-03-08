#!/bin/bash
# Script para configurar exposição dos LLMs pela internet
# Opções: Cloudflare Tunnel, ngrok, ou localtunnel

echo "=== Configuração de Tunnel para LLMs ==="
echo ""

# Verificar se cloudflared está instalado
if ! command -v cloudflared &> /dev/null; then
        echo "📦 Instalando Cloudflare Tunnel..."
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64|amd64) FILE_NAME=cloudflared-linux-amd64.deb ;; 
            aarch64|arm64) FILE_NAME=cloudflared-linux-arm64.deb ;; 
            *) FILE_NAME=cloudflared-linux-amd64.deb ;;
        esac
        TMPFILE="/tmp/${FILE_NAME}"
        DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/${FILE_NAME}"
        echo "➡️  Baixando ${DOWNLOAD_URL}"
        curl -fsSL -o "$TMPFILE" "$DOWNLOAD_URL"
        if command -v dpkg &> /dev/null; then
            sudo dpkg -i "$TMPFILE" || sudo apt-get -f install -y
        else
            echo "Instalador .deb detectado mas dpkg não encontrado; extraindo binário..."
            mkdir -p /tmp/cloudflared-tmp
            dpkg-deb -x "$TMPFILE" /tmp/cloudflared-tmp || true
            if [ -f /tmp/cloudflared-tmp/usr/local/bin/cloudflared ]; then
                sudo install -m 0755 /tmp/cloudflared-tmp/usr/local/bin/cloudflared /usr/local/bin/cloudflared
            fi
            rm -rf /tmp/cloudflared-tmp
        fi
        rm -f "$TMPFILE"
fi

echo ""
echo "✅ Cloudflared instalado!"
echo ""
echo "=== OPÇÕES DE EXPOSIÇÃO ==="
echo ""
echo "1️⃣  QUICK TUNNEL (Mais fácil - URL temporária)"
echo "   Executa: cloudflared tunnel --url http://localhost:11434"
echo "   - Gera URL tipo: https://random-name.trycloudflare.com"
echo "   - Não precisa de conta Cloudflare"
echo "   - URL muda a cada reinício"
echo ""
echo "2️⃣  TUNNEL PERMANENTE (Precisa de domínio no Cloudflare)"
echo "   - URL fixa tipo: https://ollama.seudominio.com"
echo "   - Precisa fazer login: cloudflared tunnel login"
echo ""
echo "=== INICIANDO QUICK TUNNEL ==="
echo ""

# Iniciar tunnel para Ollama (quick tunnel em foreground com trap para encerrar corretamente)
echo "🚀 Expondo Ollama (porta 11434)..."
trap 'echo "Encerrando tunnel..."; pkill -P $$ || true; exit 0' INT TERM EXIT
cloudflared tunnel --url http://localhost:11434 &
CHILD_PID=$!

sleep 2
echo ""
echo "📋 Para expor outros serviços, abra outro terminal e execute:"
echo "   cloudflared tunnel --url http://localhost:8001  # RAG API"
echo "   cloudflared tunnel --url http://localhost:8502  # GitHub Agent"
echo ""
echo "⚠️  Pressione Ctrl+C para encerrar o tunnel"
wait $CHILD_PID
trap - INT TERM EXIT
