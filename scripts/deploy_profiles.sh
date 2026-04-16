#!/bin/bash
# deploy_profiles.sh — Deploy de agentes dual-profile no servidor
# Uso: sudo bash deploy_profiles.sh [--enable-only] [--full-deploy]
#
# Este script:
# 1. Cria envfiles com portas únicas para cada instância
# 2. Atualiza o template systemd
# 3. Habilita as novas instâncias
# 4. (com --full-deploy) Para o serviço antigo e inicia os novos
#
# ATENÇÃO: --full-deploy para o btc-trading-agent.service atual!

set -euo pipefail

AGENT_DIR="/apps/crypto-trader/trading/btc_trading_agent"
ENVDIR="/apps/crypto-trader/envfiles"

# Mapeamento de instâncias → portas
# Formato: INSTANCIA:METRICS_PORT:API_PORT
declare -a INSTANCES=(
    "BTC_USDT_conservative:9100:8510"
    "BTC_USDT_aggressive:9101:8511"
    "ETH_USDT_conservative:9102:8512"
    "ETH_USDT_aggressive:9103:8513"
    "XRP_USDT_conservative:9104:8514"
    "XRP_USDT_aggressive:9105:8515"
    "SOL_USDT_conservative:9106:8516"
    "SOL_USDT_aggressive:9107:8517"
    "DOGE_USDT_conservative:9108:8518"
    "DOGE_USDT_aggressive:9109:8519"
    "ADA_USDT_conservative:9110:8520"
    "ADA_USDT_aggressive:9111:8521"
)

echo "═══════════════════════════════════════════"
echo "  Dual-Profile Trading Agent Deployment"
echo "═══════════════════════════════════════════"

# 1. Criar diretório de envfiles
mkdir -p "${ENVDIR}"
echo "📁 Criando envfiles em ${ENVDIR}..."

for entry in "${INSTANCES[@]}"; do
    IFS=':' read -r inst metrics_port api_port <<< "$entry"
    cat > "${ENVDIR}/${inst}.env" << EOF
# Auto-generated for crypto-agent@${inst}
METRICS_PORT=${metrics_port}
BTC_ENGINE_API_PORT=${api_port}
COIN_SYMBOL=$(echo "$inst" | sed 's/_conservative\|_aggressive//' | sed 's/_/-/')
EOF
    echo "  ✅ ${inst}.env (metrics:${metrics_port}, api:${api_port})"
done

# 2. Atualizar template systemd
echo ""
echo "📋 Atualizando template systemd..."
cp /home/edenilson/eddie-auto-dev/systemd/crypto-agent@.service /etc/systemd/system/crypto-agent@.service 2>/dev/null || \
    cp "${AGENT_DIR}/systemd/crypto-agent@.service" /etc/systemd/system/crypto-agent@.service 2>/dev/null || \
    echo "⚠️  Template não encontrado localmente, mantendo existente"

systemctl daemon-reload
echo "  ✅ systemd daemon-reload"

# 3. Habilitar instâncias
echo ""
echo "🔗 Habilitando instâncias..."
for entry in "${INSTANCES[@]}"; do
    inst=$(echo "$entry" | cut -d: -f1)
    systemctl enable "crypto-agent@${inst}.service" 2>/dev/null || true
    echo "  ✅ crypto-agent@${inst} enabled"
done

# 4. Deploy completo (somente com --full-deploy)
if [[ "${1:-}" == "--full-deploy" ]]; then
    echo ""
    echo "⚠️  FULL DEPLOY — Parando serviço atual e iniciando novos"
    echo "Aguardando 5s para cancelar (Ctrl+C)..."
    sleep 5

    # Parar serviço antigo
    echo "🛑 Parando btc-trading-agent.service..."
    systemctl stop btc-trading-agent.service
    systemctl disable btc-trading-agent.service

    # Iniciar novas instâncias (apenas BTC por segurança)
    echo "🚀 Iniciando instâncias BTC..."
    systemctl start crypto-agent@BTC_USDT_conservative.service
    systemctl start crypto-agent@BTC_USDT_aggressive.service
    sleep 3
    systemctl status crypto-agent@BTC_USDT_conservative.service --no-pager -l || true
    systemctl status crypto-agent@BTC_USDT_aggressive.service --no-pager -l || true
else
    echo ""
    echo "ℹ️  Modo --enable-only: instâncias habilitadas mas NÃO iniciadas"
    echo "   Para deploy completo: sudo bash deploy_profiles.sh --full-deploy"
    echo ""
    echo "   Para iniciar manualmente:"
    echo "   sudo systemctl stop btc-trading-agent.service"
    echo "   sudo systemctl start crypto-agent@BTC_USDT_conservative"
    echo "   sudo systemctl start crypto-agent@BTC_USDT_aggressive"
fi

echo ""
echo "✅ Deploy concluído!"
