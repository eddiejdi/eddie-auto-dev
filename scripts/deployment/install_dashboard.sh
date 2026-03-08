#!/bin/bash
# Instalador do Dashboard Centralizado Home Lab
# Autor: Shared Auto Dev
# Data: $(date +%Y-%m-%d)

set -e

echo "🖥️ Instalando Dashboard Centralizado Home Lab..."

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variáveis
PROJECT_DIR="/home/homelab/myClaude"
SERVICE_FILE="homelab-dashboard.service"
DASHBOARD_PORT=8500

echo -e "${BLUE}📦 Verificando dependências...${NC}"

# Instalar dependências Python
pip3 install --user streamlit requests python-dotenv 2>/dev/null || \
pip3 install streamlit requests python-dotenv --break-system-packages

echo -e "${BLUE}🔧 Configurando serviço systemd...${NC}"

# Copiar arquivo de serviço
sudo cp "${PROJECT_DIR}/${SERVICE_FILE}" /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar e iniciar serviço
sudo systemctl enable homelab-dashboard
sudo systemctl start homelab-dashboard

# Verificar status
sleep 3
if systemctl is-active --quiet homelab-dashboard; then
    echo -e "${GREEN}✅ Dashboard instalado com sucesso!${NC}"
    echo -e "${GREEN}🌐 Acesse: http://192.168.15.2:${DASHBOARD_PORT}${NC}"
else
    echo "❌ Erro ao iniciar o dashboard"
    sudo systemctl status homelab-dashboard
    exit 1
fi

# Mostrar status
echo ""
echo "📊 Status do Dashboard:"
sudo systemctl status homelab-dashboard --no-pager

echo ""
echo -e "${GREEN}✅ Instalação concluída!${NC}"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status homelab-dashboard  - Ver status"
echo "  sudo systemctl restart homelab-dashboard - Reiniciar"
echo "  sudo journalctl -u homelab-dashboard -f  - Ver logs"
