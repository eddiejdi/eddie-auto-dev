#!/bin/bash

# ================================================================
# BTC Trading Engine - Instalação e Configuração
# ================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/home/homelab/myClaude/btc_trading_agent"
SERVICE_USER="shared"

echo "=========================================="
echo "  BTC Trading Engine - Instalação"
echo "=========================================="

# Verificar se está rodando como root para instalação de serviços
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Execute como root para instalar serviços systemd"
    echo "   sudo $0"
    exit 1
fi

# 1. Criar diretório de instalação
echo ""
echo "📁 Criando estrutura de diretórios..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/models"

# 2. Copiar arquivos (assumindo que já existem)
echo "📂 Verificando arquivos necessários..."
REQUIRED_FILES=(
    "kucoin_api.py"
    "fast_model.py"
    "training_db.py"
    "trading_agent.py"
    "trading_engine.py"
    "engine_api.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$INSTALL_DIR/$file" ]; then
        echo "❌ Arquivo não encontrado: $INSTALL_DIR/$file"
        echo "   Por favor, certifique-se de que todos os arquivos Python estão no diretório"
        exit 1
    fi
done
echo "✅ Todos os arquivos necessários encontrados"

# 3. Criar arquivo de configuração padrão
echo ""
echo "⚙️  Criando configuração padrão..."
if [ ! -f "$INSTALL_DIR/config.json" ]; then
cat > "$INSTALL_DIR/config.json" << 'EOF'
{
    "enabled": false,
    "dry_run": true,
    "symbol": "BTC-USDT",
    "poll_interval": 5,
    "min_trade_interval": 60,
    "min_confidence": 0.5,
    "min_trade_amount": 10.0,
    "max_position_pct": 0.3,
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.10,
    "max_daily_trades": 20,
    "max_daily_loss": 100.0,
    "trading_hours": {
        "enabled": false,
        "start": "00:00",
        "end": "23:59"
    },
    "kucoin": {
        "api_key": "",
        "api_secret": "",
        "api_passphrase": ""
    }
}
EOF
    echo "✅ Arquivo config.json criado"
else
    echo "✅ Arquivo config.json já existe"
fi

# 4. Criar arquivo de credenciais (template)
if [ ! -f "$INSTALL_DIR/.env" ]; then
cat > "$INSTALL_DIR/.env" << 'EOF'
# KuCoin API Credentials
# Obtenha suas credenciais em: https://www.kucoin.com/account/api
KUCOIN_API_KEY=
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=

# Configurações opcionais
LOG_LEVEL=INFO
DRY_RUN=true
EOF
    chmod 600 "$INSTALL_DIR/.env"
    echo "✅ Arquivo .env template criado"
else
    echo "✅ Arquivo .env já existe"
fi

# 5. Instalar serviço systemd - Trading Engine
echo ""
echo "🔧 Instalando serviço systemd para Trading Engine..."
cat > /etc/systemd/system/btc-trading-engine.service << EOF
[Unit]
Description=BTC Trading Engine - Automated 24/7 Trading
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $INSTALL_DIR/trading_engine.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

# Limites de recursos
MemoryLimit=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
echo "✅ Serviço btc-trading-engine.service instalado"

# 6. Instalar serviço systemd - API
echo "🔧 Instalando serviço systemd para Engine API..."
cat > /etc/systemd/system/btc-engine-api.service << EOF
[Unit]
Description=BTC Trading Engine API - HTTP Control Interface
After=network.target btc-trading-engine.service
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
Environment=API_PORT=8511
ExecStart=/usr/bin/python3 $INSTALL_DIR/engine_api.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "✅ Serviço btc-engine-api.service instalado"

# 7. Recarregar systemd
echo ""
echo "🔄 Recarregando systemd..."
systemctl daemon-reload

# 8. Ajustar permissões
echo "🔐 Ajustando permissões..."
chown -R $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"
chmod 644 "$INSTALL_DIR"/*.py
chmod 600 "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/config.json"

echo ""
echo "=========================================="
echo "  ✅ Instalação Concluída!"
echo "=========================================="
echo ""
echo "📋 Próximos passos:"
echo ""
echo "1. Configure suas credenciais KuCoin:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Ajuste as configurações de trading:"
echo "   nano $INSTALL_DIR/config.json"
echo ""
echo "3. Habilite e inicie os serviços:"
echo "   sudo systemctl enable btc-engine-api"
echo "   sudo systemctl start btc-engine-api"
echo ""
echo "4. (Opcional) Inicie o engine de trading:"
echo "   sudo systemctl enable btc-trading-engine"
echo "   sudo systemctl start btc-trading-engine"
echo ""
echo "5. Verifique o status:"
echo "   sudo systemctl status btc-engine-api"
echo "   sudo systemctl status btc-trading-engine"
echo ""
echo "6. Veja os logs:"
echo "   journalctl -u btc-engine-api -f"
echo "   journalctl -u btc-trading-engine -f"
echo ""
echo "🌐 API disponível em: http://localhost:8511"
echo "📊 Painel de controle: ${OPENWEBUI_URL:-http://${HOMELAB_HOST:-localhost}:3000} (Open WebUI → Settings → Integrations → BTC Trading)"
echo ""
echo "⚠️  IMPORTANTE: O modo DRY_RUN está ativado por padrão!"
echo "   Desative apenas quando estiver pronto para trading real."
echo ""
