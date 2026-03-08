#!/bin/bash
#
# Script de Instalação do WhatsApp Bot com WAHA
# Este script configura o WAHA (WhatsApp HTTP API) via Docker
# e o bot Python que se conecta a ele
#
# Número: 5511981193899
#

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     Instalação do WhatsApp Bot com WAHA          ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Diretório base
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$BASE_DIR/whatsapp_data"

# Criar diretórios necessários
echo -e "${YELLOW}[1/6] Criando diretórios...${NC}"
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/sessions"

# Verificar Docker
echo -e "${YELLOW}[2/6] Verificando Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker não encontrado! Instalando...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker instalado! Faça logout e login novamente.${NC}"
fi

# Verificar se Docker está rodando
if ! docker info &> /dev/null; then
    echo -e "${YELLOW}Iniciando Docker...${NC}"
    sudo systemctl start docker
fi

# Parar container existente se houver
echo -e "${YELLOW}[3/6] Configurando WAHA (WhatsApp HTTP API)...${NC}"
docker stop waha 2>/dev/null || true
docker rm waha 2>/dev/null || true

# Criar arquivo de configuração do WAHA
cat > "$DATA_DIR/waha.config.json" << 'EOF'
{
  "port": 3000,
  "sessions": {
    "shared": {
      "engine": "WEBJS",
      "webhooks": [
        {
          "url": "http://host.docker.internal:5001/webhook",
          "events": ["message", "message.any", "session.status"]
        }
      ]
    }
  }
}
EOF

# Baixar e iniciar WAHA
echo -e "${YELLOW}[4/6] Iniciando container WAHA...${NC}"
docker run -d \
    --name waha \
    --restart unless-stopped \
    -p 3000:3000 \
    -e WHATSAPP_HOOK_URL=http://host.docker.internal:5001/webhook \
    -e WHATSAPP_HOOK_EVENTS=message,message.any,session.status \
    -e WAHA_PRINT_QR=true \
    -e WHATSAPP_DEFAULT_ENGINE=WEBJS \
    -v "$DATA_DIR/sessions:/app/.sessions" \
    devlikeapro/waha:latest

# Aguardar container iniciar
echo -e "${YELLOW}Aguardando WAHA iniciar...${NC}"
sleep 10

# Verificar status
if docker ps | grep -q waha; then
    echo -e "${GREEN}✅ WAHA iniciado com sucesso!${NC}"
else
    echo -e "${RED}❌ Erro ao iniciar WAHA${NC}"
    docker logs waha
    exit 1
fi

# Instalar dependências Python
echo -e "${YELLOW}[5/6] Instalando dependências Python...${NC}"
pip3 install --user httpx aiohttp python-dotenv 2>/dev/null || \
pip install --user httpx aiohttp python-dotenv

# Criar arquivo .env
echo -e "${YELLOW}[6/6] Criando arquivo de configuração...${NC}"
cat > "$BASE_DIR/.env.whatsapp" << EOF
# Configuração do WhatsApp Bot
WHATSAPP_NUMBER=5511981193899
WAHA_URL=http://localhost:3004
WAHA_API_KEY=

# IA
OLLAMA_HOST=http://${HOMELAB_HOST:-192.168.15.2}:11434
OLLAMA_MODEL=shared-coder
OPENWEBUI_HOST=http://${HOMELAB_HOST:-192.168.15.2}:3000

# Admin (números separados por vírgula)
ADMIN_NUMBERS=5511981193899
EOF

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Instalação Concluída com Sucesso!         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📱 Próximos passos:${NC}"
echo ""
echo "1. Acesse o QR Code para conectar o WhatsApp:"
echo -e "   ${YELLOW}http://localhost:3000/api/sessions/shared/auth/qr${NC}"
echo ""
echo "2. Ou veja os logs do WAHA para o QR no terminal:"
echo -e "   ${YELLOW}docker logs -f waha${NC}"
echo ""
echo "3. Escaneie o QR Code com o WhatsApp do número 5511981193899"
echo ""
echo "4. Inicie o bot:"
echo -e "   ${YELLOW}source .env.whatsapp && python3 whatsapp_bot.py${NC}"
echo ""
echo "5. Ou use o serviço systemd:"
echo -e "   ${YELLOW}sudo systemctl start shared-whatsapp.service${NC}"
echo ""
echo -e "${GREEN}Webhook configurado em: http://localhost:5001/webhook${NC}"
echo ""
