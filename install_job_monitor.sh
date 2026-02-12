#!/bin/bash
#
# Script de instalação do Sistema de Aplicação Automática de Vagas
# Deploy no homelab com todas as melhorias implementadas
#

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  📦 INSTALAÇÃO - Sistema de Aplicação Automática de Vagas"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
HOMELAB_USER="${HOMELAB_USER:-homelab}"
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
REPO_PATH="/home/$HOMELAB_USER/eddie-auto-dev"
VENV_PATH="/home/$HOMELAB_USER/docling_venv"

echo -e "${GREEN}✓${NC} Configuração:"
echo "   Host: $HOMELAB_HOST"
echo "   Usuário: $HOMELAB_USER"
echo "   Repo: $REPO_PATH"
echo "   Venv: $VENV_PATH"
echo ""

# Check connectivity
echo -e "${YELLOW}→${NC} Verificando conexão com homelab..."
if ! ssh -o ConnectTimeout=10 "$HOMELAB_USER@$HOMELAB_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Não foi possível conectar ao homelab"
    echo "   Verifique SSH e configuração de rede"
    exit 1
fi
echo -e "${GREEN}✓${NC} Conexão OK"
echo ""

# Copy files
echo -e "${YELLOW}→${NC} Copiando arquivos para homelab..."
scp -q apply_real_job.py "$HOMELAB_USER@$HOMELAB_HOST:$REPO_PATH/" && echo -e "${GREEN}✓${NC} apply_real_job.py"
scp -q job_monitor_continuous.py "$HOMELAB_USER@$HOMELAB_HOST:$REPO_PATH/" && echo -e "${GREEN}✓${NC} job_monitor_continuous.py"
scp -q dashboard_job_monitor.py "$HOMELAB_USER@$HOMELAB_HOST:$REPO_PATH/" && echo -e "${GREEN}✓${NC} dashboard_job_monitor.py"
scp -q compatibility_*.py "$HOMELAB_USER@$HOMELAB_HOST:$REPO_PATH/" 2>/dev/null && echo -e "${GREEN}✓${NC} compatibility modules" || echo -e "${YELLOW}⚠${NC} compatibility modules not found (optional)"
echo ""

# Check dependencies
echo -e "${YELLOW}→${NC} Verificando dependências no homelab..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "source $VENV_PATH/bin/activate && python3 -c 'import reportlab, google.oauth2, sentence_transformers' && echo 'Dependencies OK'" 2>/dev/null && echo -e "${GREEN}✓${NC} Todas as dependências instaladas" || {
    echo -e "${YELLOW}⚠${NC} Instalando dependências faltantes..."
    ssh "$HOMELAB_USER@$HOMELAB_HOST" "source $VENV_PATH/bin/activate && pip install -q reportlab google-auth-oauthlib google-api-python-client sentence_transformers scikit-learn torch"
    echo -e "${GREEN}✓${NC} Dependências instaladas"
}
echo ""

# Setup systemd service
echo -e "${YELLOW}→${NC} Configurando serviço systemd..."
if [ -f "systemd/job-monitor.service" ]; then
    scp -q systemd/job-monitor.service "$HOMELAB_USER@$HOMELAB_HOST:/tmp/"
    ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo mv /tmp/job-monitor.service /etc/systemd/system/ && sudo systemctl daemon-reload"
    echo -e "${GREEN}✓${NC} Serviço systemd configurado"
else
    echo -e "${YELLOW}⚠${NC} Arquivo systemd/job-monitor.service não encontrado (skip)"
fi
echo ""

# Permissions
echo -e "${YELLOW}→${NC} Ajustando permissões..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "chmod +x $REPO_PATH/*.py"
echo -e "${GREEN}✓${NC} Permissões ajustadas"
echo ""

# Test run
echo -e "${YELLOW}→${NC} Testando execução básica..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "cd $REPO_PATH && source $VENV_PATH/bin/activate && python3 -c 'from apply_real_job import CURRICULUM_TEXT; print(\"Import OK:\", len(CURRICULUM_TEXT), \"chars\")'" && echo -e "${GREEN}✓${NC} Teste de importação OK" || {
    echo -e "${RED}✗${NC} Falha no teste de importação"
    exit 1
}
echo ""

# Dashboard test
echo -e "${YELLOW}→${NC} Testando dashboard..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "cd $REPO_PATH && source $VENV_PATH/bin/activate && python3 dashboard_job_monitor.py" 2>/dev/null && echo -e "${GREEN}✓${NC} Dashboard OK" || echo -e "${YELLOW}⚠${NC} Dashboard test failed (optional)"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ INSTALAÇÃO CONCLUÍDA!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📋 Próximos Passos:"
echo ""
echo "1️⃣  Executar busca única:"
echo "   ssh $HOMELAB_USER@$HOMELAB_HOST"
echo "   cd $REPO_PATH && source $VENV_PATH/bin/activate"
echo "   python3 apply_real_job.py"
echo ""
echo "2️⃣  Iniciar monitoramento contínuo:"
echo "   ssh $HOMELAB_USER@$HOMELAB_HOST"
echo "   sudo systemctl start job-monitor"
echo "   sudo systemctl enable job-monitor  # Auto-start on boot"
echo ""
echo "3️⃣  Ver dashboard:"
echo "   ssh $HOMELAB_USER@$HOMELAB_HOST"
echo "   cd $REPO_PATH && source $VENV_PATH/bin/activate"
echo "   python3 dashboard_job_monitor.py"
echo ""
echo "4️⃣  Configurar whitelist de grupos (opcional):"
echo "   sudo systemctl edit job-monitor"
echo "   Adicionar: Environment=\"GROUP_WHITELIST=grupo1@g.us,grupo2@g.us\""
echo ""
echo "5️⃣  Configurar notificações Telegram (opcional):"
echo "   sudo systemctl edit job-monitor"
echo "   Adicionar:"
echo "      Environment=\"TELEGRAM_BOT_TOKEN=seu_token\""
echo "      Environment=\"TELEGRAM_CHAT_ID=seu_chat_id\""
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
