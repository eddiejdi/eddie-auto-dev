#!/bin/bash
# 🔧 BTC Trading Agent - Recovery Script
# Autor: AutoDev Agent
# Data: 2026-02-26
# Proposito: Limpar estado corrompido e reiniciar agente em modo seguro

set -e

AGENT_HOME="/home/homelab/myClaude/btc_trading_agent"
DB_PATH="${AGENT_HOME}/data/trading_agent.db"
CONFIG_PATH="${AGENT_HOME}/config.json"

echo "🔴 [BTC Recovery] Iniciando recuperação do agente de trading..."

# 1. Backup do DB atual
echo "📦 [Step 1] Fazendo backup do banco de dados..."
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "${DB_PATH}.backup.$(date +%s)"
    echo "✅ Backup criado"
else
    echo "⚠️  DB não encontrado"
fi

# 2. Limpar posição travada
echo "🔓 [Step 2] Limpando posição travada..."
sqlite3 "$DB_PATH" <<EOF
-- Marcar última posição BUY aberta como force_closed
UPDATE trades 
SET status = 'force_closed'
WHERE dry_run = 0 
  AND side = 'buy' 
  AND (SELECT COUNT(*) FROM trades t2 
       WHERE t2.side='sell' 
       AND t2.timestamp > trades.timestamp 
       AND t2.dry_run=0) = 0
  LIMIT 1;

-- Verificar
SELECT 'Posições abertas após limpeza:';
SELECT id, timestamp, side, status FROM trades 
WHERE dry_run = 0 
ORDER BY timestamp DESC LIMIT 5;
EOF
echo "✅ Posição travada marcada como closed"

# 3. Parar processos do agente
echo "🛑 [Step 3] Parando processos do agente..."
pkill -f "trading_agent.py" || true
pkill -f "webui_integration.py" || true
pkill -f "prometheus_exporter.py" --port 9092 || true
sleep 3
echo "✅ Processos parados"

# 4. Resetar config para modo seguro (dry-run)
echo "⚙️  [Step 4] Configurando para modo SAFE (dry-run)..."
if [ -f "$CONFIG_PATH" ]; then
    # Usar jq se disponível, senão sed
    if command -v jq &> /dev/null; then
        jq '.live_trading = false | .dry_run = true | .pause_on_loss = true' "$CONFIG_PATH" > "${CONFIG_PATH}.tmp"
        mv "${CONFIG_PATH}.tmp" "$CONFIG_PATH"
    else
        # Fallback: sed basic
        sed -i 's/"live_trading": true/"live_trading": false/g' "$CONFIG_PATH"
        sed -i 's/"dry_run": false/"dry_run": true/g' "$CONFIG_PATH"
    fi
    echo "✅ Config atualizado para dry-run mode"
fi

# 5. Reiniciar agente em background
echo "🚀 [Step 5] Reiniciando agente em modo dry-run..."
cd "$AGENT_HOME"

# Iniciar trading_agent em background com dry-run
nohup python3 trading_agent.py --daemon --dry-run > /tmp/trading_agent_recovery.log 2>&1 &
AGENT_PID=$!
echo "✅ trading_agent iniciado (PID: $AGENT_PID)"

sleep 3

# Iniciar webui_integration
nohup venv/bin/python webui_integration.py --port 8510 > /tmp/webui_recovery.log 2>&1 &
WEBUI_PID=$!
echo "✅ webui_integration iniciado (PID: $WEBUI_PID)"

sleep 3

# 6. Testar endpoints
echo "🧪 [Step 6] Testando endpoints..."
if curl -s http://localhost:8511/health | grep -q "healthy"; then
    echo "✅ Engine API respondendo"
else
    echo "❌ Engine API não respondendo"
fi

if curl -s http://localhost:8510/api/status | grep -q "online"; then
    echo "✅ WebUI respondendo"
else
    echo "⚠️  WebUI ainda inicializando..."
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ RECUPERAÇÃO COMPLETA"
echo "════════════════════════════════════════════════════════"
echo "Modo: DRY-RUN (sem dinheiro em risco)"
echo "Banco de dados: Backup em ${DB_PATH}.backup.*"
echo "Comportamento esperado:"
echo "  - Trades em modo dry-run apenas"
echo "  - Métricas de performance serão resetadas"
echo "  - WebUI em http://192.168.15.2:8510"
echo "  - Dashboard em http://192.168.15.2:3002/d/btc-trading-monitor"
echo ""
echo "Próximos passos:"
echo "  1. Monitorar performance por 1-2h"
echo "  2. Se win_rate > 50% em dry-run, fazer re-treinamento em live"
echo "  3. Reconfigurar config.json com live_trading=true quando estável"
echo ""
echo "Para mudar para LIVE:"
echo "  sed -i 's/\"live_trading\": false/\"live_trading\": true/' $CONFIG_PATH"
echo "  systemctl restart trading-agent (ou pkill + reiniciar)"
