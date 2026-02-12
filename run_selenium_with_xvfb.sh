#!/bin/bash
# 🤖 Agent Selenium com Display Virtual

set -e

DISPLAY_NUM=99
DISPLAY_PORT=$((5900 + DISPLAY_NUM))

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║            🤖 AGENT SELENIUM - AUTENTICAÇÃO OAUTH AUTOMÁTICA            ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Iniciando ambiente virtual..."

# Verificar se Xvfb está disponível
if ! command -v Xvfb &> /dev/null; then
    echo "⚠️  Xvfb não encontrado. Instalando..."
    apt-get update -qq && apt-get install -y xvfb &>/dev/null
    echo "✅ Xvfb instalado"
fi

# Iniciar display virtual
echo "🖥️  Iniciando display virtual (DISPLAY=:$DISPLAY_NUM)..."

export DISPLAY=:$DISPLAY_NUM

Xvfb :$DISPLAY_NUM -screen 0 1280x1024x24 > /tmp/xvfb.log 2>&1 &
XVFB_PID=$!

sleep 2

echo "✅ Display virtual iniciado (PID: $XVFB_PID)"

# Executar agent Selenium
echo ""
echo "🤖 Executando Agent Selenium..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 /home/homelab/myClaude/selenium_oauth_agent.py
AGENT_EXIT_CODE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Limpar
echo ""
echo "🧹 Limpando..."
kill $XVFB_PID 2>/dev/null || true
sleep 1

if [ $AGENT_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════╗"
    echo "║                        ✅ PROCESSO COMPLETO!                           ║"
    echo "╚════════════════════════════════════════════════════════════════════════╝"
else
    echo ""
    echo "⚠️  Agent encerrou com erro ($AGENT_EXIT_CODE)"
fi

exit $AGENT_EXIT_CODE
