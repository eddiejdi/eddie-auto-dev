#!/bin/bash
# Instalação do Gmail Expurgo Inteligente
# Configura treinamento de IA + notificações WhatsApp/Telegram

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      📧 Instalação Gmail Expurgo Inteligente v2.0 📧        ║${NC}"
echo -e "${BLUE}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║  • Limpeza inteligente de emails                            ║${NC}"
echo -e "${BLUE}║  • Treinamento da IA Shared                                  ║${NC}"
echo -e "${BLUE}║  • Notificações WhatsApp/Telegram                           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar se é root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️ Executando sem sudo - algumas operações podem falhar${NC}"
fi

BASE_DIR="/home/homelab/myClaude"
cd "$BASE_DIR"

# 1. Instalar dependências Python
echo -e "${YELLOW}[1/5] Instalando dependências Python...${NC}"
pip3 install --quiet --upgrade \
    google-auth \
    google-auth-oauthlib \
    google-auth-httplib2 \
    google-api-python-client \
    chromadb \
    httpx \
    requests \
    pydantic \
    2>/dev/null || echo "Algumas dependências podem já estar instaladas"

echo -e "${GREEN}✅ Dependências instaladas${NC}"

# 2. Verificar/Criar diretórios
echo -e "${YELLOW}[2/5] Verificando diretórios...${NC}"

mkdir -p "$BASE_DIR/gmail_data"
mkdir -p "$BASE_DIR/chroma_db"
mkdir -p "$BASE_DIR/email_training_data"
mkdir -p "$BASE_DIR/training_data"

echo -e "${GREEN}✅ Diretórios criados${NC}"

# 3. Verificar token Gmail
echo -e "${YELLOW}[3/5] Verificando autenticação Gmail...${NC}"

if [ -f "$BASE_DIR/gmail_data/token.json" ]; then
    echo -e "${GREEN}✅ Token Gmail encontrado${NC}"
else
    echo -e "${RED}⚠️ Token Gmail não encontrado!${NC}"
    echo -e "${YELLOW}Execute: python3 gmail_oauth_local.py${NC}"
fi

# 4. Configurar variáveis de ambiente
echo -e "${YELLOW}[4/5] Configurando variáveis de ambiente...${NC}"

ENV_FILE="$BASE_DIR/.env.expurgo"
cat > "$ENV_FILE" << 'EOF'
# Configurações do Gmail Expurgo Inteligente
OLLAMA_HOST=http://192.168.15.2:11434
WAHA_URL=http://localhost:3001
GMAIL_DATA_DIR=/home/homelab/myClaude/gmail_data
# TELEGRAM_BOT_TOKEN should be provided via environment or the repo vault.
# Example: use tools/simple_vault/export_env.sh to populate /etc/default/<unit>
TELEGRAM_BOT_TOKEN=""
ADMIN_CHAT_ID=YOUR_CHAT_ID
ADMIN_PHONE=5511999999999
EOF

echo -e "${GREEN}✅ Arquivo .env.expurgo criado${NC}"
echo -e "${YELLOW}   Edite com suas configurações reais!${NC}"

# 5. Instalar serviço systemd
echo -e "${YELLOW}[5/5] Instalando serviço systemd...${NC}"

if [ "$EUID" -eq 0 ]; then
    cp "$BASE_DIR/shared-expurgo.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable shared-expurgo.service
    echo -e "${GREEN}✅ Serviço systemd instalado${NC}"
    echo -e "${YELLOW}   Para iniciar: sudo systemctl start shared-expurgo${NC}"
else
    echo -e "${YELLOW}⚠️ Execute com sudo para instalar o serviço systemd${NC}"
    echo -e "${YELLOW}   sudo cp shared-expurgo.service /etc/systemd/system/${NC}"
fi

# Resumo
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ Instalação Concluída!                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📋 Próximos passos:${NC}"
echo ""
echo -e "1. ${YELLOW}Configure suas credenciais:${NC}"
echo "   nano $BASE_DIR/.env.expurgo"
echo ""
echo -e "2. ${YELLOW}Teste em modo simulação:${NC}"
echo "   python3 $BASE_DIR/gmail_expurgo_inteligente.py"
echo ""
echo -e "3. ${YELLOW}Execute de verdade:${NC}"
echo "   python3 $BASE_DIR/gmail_expurgo_inteligente.py --execute"
echo ""
echo -e "4. ${YELLOW}Inicie o serviço (24/7):${NC}"
echo "   sudo systemctl start shared-expurgo"
echo "   sudo systemctl status shared-expurgo"
echo ""
echo -e "${BLUE}📚 Documentação: README_EXPURGO.md${NC}"
