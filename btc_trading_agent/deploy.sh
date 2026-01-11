#!/bin/bash
#===============================================================
# Bitcoin Trading Agent - Deploy Script
# Instala e configura o agente de trading 24/7
#===============================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AGENT_DIR="/home/eddie/myClaude/btc_trading_agent"
SERVICE_NAME="btc-trading-agent"

echo -e "${BLUE}"
echo "=========================================="
echo "  Bitcoin Trading Agent 24/7 - Deploy"
echo "=========================================="
echo -e "${NC}"

# Verificar se está rodando como root para instalar serviço
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Para instalar o serviço systemd, execute com sudo${NC}"
        echo ""
    fi
}

# Instalar dependências Python
install_dependencies() {
    echo -e "${BLUE}📦 Instalando dependências Python...${NC}"
    
    pip3 install --user requests aiohttp numpy pandas 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Instalando com pip básico...${NC}"
        pip install requests 2>/dev/null || true
    }
    
    echo -e "${GREEN}✅ Dependências instaladas${NC}"
}

# Criar diretórios necessários
create_directories() {
    echo -e "${BLUE}📁 Criando diretórios...${NC}"
    
    mkdir -p "$AGENT_DIR/logs"
    mkdir -p "$AGENT_DIR/data"
    mkdir -p "$AGENT_DIR/models"
    
    echo -e "${GREEN}✅ Diretórios criados${NC}"
}

# Configurar variáveis de ambiente
setup_env() {
    echo -e "${BLUE}🔐 Configurando ambiente...${NC}"
    
    ENV_FILE="$AGENT_DIR/.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << 'EOF'
# KuCoin API Credentials
# Obtenha suas credenciais em: https://www.kucoin.com/account/api
KUCOIN_API_KEY=
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=

# Trading Configuration
TRADING_SYMBOL=BTC-USDT
DRY_RUN=true
MIN_TRADE_AMOUNT=10
MAX_POSITION_PCT=0.3
EOF
        echo -e "${YELLOW}⚠️  Edite $ENV_FILE com suas credenciais${NC}"
    else
        echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
    fi
}

# Instalar serviço systemd
install_service() {
    echo -e "${BLUE}🔧 Instalando serviço systemd...${NC}"
    
    SERVICE_FILE="$AGENT_DIR/$SERVICE_NAME.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        if [ "$EUID" -eq 0 ]; then
            cp "$SERVICE_FILE" /etc/systemd/system/
            systemctl daemon-reload
            echo -e "${GREEN}✅ Serviço instalado${NC}"
        else
            echo -e "${YELLOW}Execute: sudo cp $SERVICE_FILE /etc/systemd/system/ && sudo systemctl daemon-reload${NC}"
        fi
    fi
}

# Verificar configuração
verify_config() {
    echo -e "${BLUE}🔍 Verificando configuração...${NC}"
    
    # Verificar arquivos
    FILES=("kucoin_api.py" "fast_model.py" "training_db.py" "trading_agent.py")
    
    for file in "${FILES[@]}"; do
        if [ -f "$AGENT_DIR/$file" ]; then
            echo -e "  ${GREEN}✅${NC} $file"
        else
            echo -e "  ${RED}❌${NC} $file (MISSING)"
        fi
    done
    
    # Verificar Python
    if command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 --version)
        echo -e "  ${GREEN}✅${NC} Python: $PY_VERSION"
    else
        echo -e "  ${RED}❌${NC} Python3 não encontrado"
    fi
}

# Testar conexão com API
test_api() {
    echo -e "${BLUE}🌐 Testando conexão com KuCoin...${NC}"
    
    python3 << 'EOF'
import sys
sys.path.insert(0, "/home/eddie/myClaude/btc_trading_agent")
try:
    from kucoin_api import get_price_fast
    price = get_price_fast("BTC-USDT", timeout=5)
    if price:
        print(f"  ✅ BTC-USDT: ${price:,.2f}")
    else:
        print("  ⚠️  Preço indisponível")
except Exception as e:
    print(f"  ❌ Erro: {e}")
EOF
}

# Iniciar agente
start_agent() {
    echo -e "${BLUE}🚀 Iniciando agente...${NC}"
    
    if [ "$EUID" -eq 0 ]; then
        systemctl enable $SERVICE_NAME
        systemctl start $SERVICE_NAME
        sleep 2
        systemctl status $SERVICE_NAME --no-pager -l
    else
        echo -e "${YELLOW}Para iniciar como serviço:${NC}"
        echo "  sudo systemctl enable $SERVICE_NAME"
        echo "  sudo systemctl start $SERVICE_NAME"
        echo ""
        echo -e "${YELLOW}Para iniciar manualmente:${NC}"
        echo "  cd $AGENT_DIR"
        echo "  python3 trading_agent.py --daemon"
    fi
}

# Mostrar status
show_status() {
    echo ""
    echo -e "${BLUE}📊 Status:${NC}"
    
    if [ "$EUID" -eq 0 ] && systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "  ${GREEN}✅${NC} Serviço: RUNNING"
        echo ""
        echo "  Comandos úteis:"
        echo "    sudo systemctl status $SERVICE_NAME"
        echo "    sudo journalctl -u $SERVICE_NAME -f"
        echo "    sudo systemctl stop $SERVICE_NAME"
    else
        echo -e "  ${YELLOW}⏸️${NC}  Serviço: NOT RUNNING"
    fi
}

# Mostrar uso
show_usage() {
    echo ""
    echo -e "${BLUE}📖 Uso:${NC}"
    echo ""
    echo "  Modo Dry Run (simulação):"
    echo "    python3 $AGENT_DIR/trading_agent.py --dry-run"
    echo ""
    echo "  Modo Live (⚠️ dinheiro real!):"
    echo "    python3 $AGENT_DIR/trading_agent.py --live"
    echo ""
    echo "  Modo Daemon (background):"
    echo "    python3 $AGENT_DIR/trading_agent.py --daemon"
    echo ""
    echo "  Monitorar logs:"
    echo "    tail -f $AGENT_DIR/logs/agent.log"
    echo ""
}

# Menu principal
main() {
    case "${1:-install}" in
        install)
            check_sudo
            create_directories
            install_dependencies
            setup_env
            verify_config
            test_api
            install_service
            show_status
            show_usage
            ;;
        start)
            start_agent
            ;;
        status)
            verify_config
            show_status
            ;;
        test)
            test_api
            ;;
        *)
            echo "Uso: $0 {install|start|status|test}"
            exit 1
            ;;
    esac
}

main "$@"

echo ""
echo -e "${GREEN}=========================================="
echo "  Deploy concluído! 🎉"
echo "==========================================${NC}"
