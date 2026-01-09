#!/bin/bash
# Script para configurar exposição dos LLMs pela internet
# Opções: Cloudflare Tunnel, ngrok, ou localtunnel

echo "=== Configuração de Tunnel para LLMs ==="
echo ""

# Verificar se cloudflared está instalado
if ! command -v cloudflared &> /dev/null; then
    echo "📦 Instalando Cloudflare Tunnel..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared.deb
    rm cloudflared.deb
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

# Iniciar tunnel para Ollama
echo "🚀 Expondo Ollama (porta 11434)..."
cloudflared tunnel --url http://localhost:11434 &
OLLAMA_PID=$!

sleep 5
echo ""
echo "📋 Para expor outros serviços, abra outro terminal e execute:"
echo "   cloudflared tunnel --url http://localhost:8001  # RAG API"
echo "   cloudflared tunnel --url http://localhost:8502  # GitHub Agent"
echo ""
echo "⚠️  Pressione Ctrl+C para encerrar o tunnel"
wait $OLLAMA_PID
