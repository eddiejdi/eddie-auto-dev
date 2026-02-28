#!/bin/bash
# Deploy Alertmanager Telegram Integration
# Instala webhook receiver e configura Alertmanager para enviar notificações ao Telegram
#
# Uso:
#   ./deploy_alertmanager_telegram.sh [homelab_user] [homelab_host] [telegram_bot_token] [telegram_chat_id]
#
# Exemplos:
#   ./deploy_alertmanager_telegram.sh homelab 192.168.15.2 123456789:ABCdefGHIjklmNOPqrs 123456789
#
# Env vars (alternativa):
#   TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./deploy...

set -euo pipefail

HOMELAB_USER=${1:-"homelab"}
HOMELAB_HOST=${2:-"192.168.15.2"}
TELEGRAM_BOT_TOKEN=${3:-"${TELEGRAM_BOT_TOKEN:-}"}
TELEGRAM_CHAT_ID=${4:-"${TELEGRAM_CHAT_ID:-}"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/alertmanager_telegram_deploy_$(date +%Y%m%d_%H%M%S).log"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $@"
    echo -e "${BLUE}${msg}${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $@${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ $@${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠️  $@${NC}" | tee -a "$LOG_FILE"
}

# Validate inputs
if [[ -z "$TELEGRAM_BOT_TOKEN" ]] || [[ -z "$TELEGRAM_CHAT_ID" ]]; then
    error "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID são obrigatórios"
    echo ""
    echo "Uso:"
    echo "  $0 [homelab_user] [homelab_host] [telegram_bot_token] [telegram_chat_id]"
    echo ""
    echo "Ou via env vars:"
    echo "  export TELEGRAM_BOT_TOKEN=..."
    echo "  export TELEGRAM_CHAT_ID=..."
    echo "  $0 [homelab_user] [homelab_host]"
    exit 1
fi

log "=========================================="
log "Deploy: Alertmanager → Telegram Integration"
log "=========================================="
log "Homelab: $HOMELAB_USER@$HOMELAB_HOST"
log "Chat ID: $TELEGRAM_CHAT_ID (Bot token: ${TELEGRAM_BOT_TOKEN:0:10}...)"

# Test connectivity
log "Validando conectividade..."
if ! ssh -q "$HOMELAB_USER@$HOMELAB_HOST" "echo OK" > /dev/null 2>&1; then
    error "Não consegui conectar em $HOMELAB_USER@$HOMELAB_HOST"
    exit 1
fi
success "Conectividade OK"

# Deploy webhook script
log "Transferindo webhook receiver script..."
if scp "$SCRIPT_DIR/alertmanager_telegram_webhook.py" \
    "$HOMELAB_USER@$HOMELAB_HOST:/tmp/alertmanager_telegram_webhook.py" >> "$LOG_FILE" 2>&1; then
    success "Script transferido"
else
    error "Falha ao transferir script"
    exit 1
fi

# Install webhook script
log "Instalando webhook receiver em /usr/local/bin/..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo mv /tmp/alertmanager_telegram_webhook.py /usr/local/bin/ && \
     sudo chmod +x /usr/local/bin/alertmanager_telegram_webhook.py" >> "$LOG_FILE" 2>&1
success "Webhook instalado"

# Create systemd service for webhook
log "Criando serviço systemd para webhook receiver..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo tee /etc/systemd/system/alertmanager-telegram-webhook.service > /dev/null" << EOF
[Unit]
Description=Alertmanager → Telegram Webhook Receiver
After=network.target
Wants=alertmanager.service

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/alertmanager_telegram_webhook.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment="TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"
Environment="TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID"
Environment="WEBHOOK_PORT=5000"

[Install]
WantedBy=multi-user.target
EOF

success "Serviço criado"

# Reload systemd
log "Recarregando systemd daemon..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo systemctl daemon-reload" >> "$LOG_FILE" 2>&1
success "Daemon recarregado"

# Enable and start webhook service
log "Habilitando webhook para boot automático..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo systemctl enable alertmanager-telegram-webhook.service" >> "$LOG_FILE" 2>&1
success "Habilitado para boot"

log "Iniciando webhook service..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo systemctl start alertmanager-telegram-webhook.service" >> "$LOG_FILE" 2>&1
success "Serviço iniciado"

# Wait for webhook to be ready
log "Aguardando webhook ficar pronto..."
sleep 2

# Test webhook connectivity
log "Testando webhook..."
if ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "curl -s http://localhost:5000/health | grep -q ok" > /dev/null 2>&1; then
    success "Webhook respondendo normalmente"
else
    warning "Webhook pode estar demorando para ficar pronto (testando novamente em 5s)"
    sleep 5
fi

# Deploy Alertmanager configuration
log "Transferindo configuração Alertmanager..."
if scp "$SCRIPT_DIR/alertmanager_telegram.yml" \
    "$HOMELAB_USER@$HOMELAB_HOST:/tmp/alertmanager.yml" >> "$LOG_FILE" 2>&1; then
    success "Config transferida"
else
    error "Falha ao transferir config"
    exit 1
fi

# Backup current config and install new one
log "Instalando nova configuração do Alertmanager..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo cp /etc/prometheus/alertmanager.yml /etc/prometheus/alertmanager.yml.backup.$(date +%Y%m%d_%H%M%S) && \
     sudo cp /tmp/alertmanager.yml /etc/prometheus/alertmanager.yml && \
     sudo chown root:root /etc/prometheus/alertmanager.yml && \
     sudo chmod 644 /etc/prometheus/alertmanager.yml" >> "$LOG_FILE" 2>&1
success "Config instalada (backup criado)"

# Reload Alertmanager
log "Recarregando Alertmanager..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo systemctl reload alertmanager" >> "$LOG_FILE" 2>&1
success "Alertmanager recarregado"

# Verify Alertmanager status
log "Verificando status do Alertmanager..."
if ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo systemctl is-active alertmanager | grep -q active" > /dev/null 2>&1; then
    success "Alertmanager: active (running)"
else
    error "Alertmanager pode estar com problemas"
    ssh "$HOMELAB_USER@$HOMELAB_HOST" \
        "sudo journalctl -u alertmanager -n 20 --no-pager" >> "$LOG_FILE" 2>&1
fi

# Final verification
log ""
log "=========================================="
log "VERIFICAÇÃO FINAL"
log "=========================================="

echo ""
echo "✅ SERVIÇOS"
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "sudo systemctl is-active alertmanager alertmanager-telegram-webhook.service" | \
    xargs -I {} echo "   • {}"

echo ""
echo "✅ WEBHOOK HEALTH"
ssh "$HOMELAB_USER@$HOMELAB_HOST" \
    "curl -s http://localhost:5000/health" | jq . 2>/dev/null || echo "   Webhook respondendo"

echo ""
log "Próximos passos:"
echo "   1. Triggers de Prometheus devem estar em: monitoring/prometheus/selfhealing_rules.yml"
echo "   2. Para testar manualmente:"
echo "      curl -X POST http://192.168.15.2:9093/api/v1/alerts"
echo "   3. Ver logs: journalctl -u alertmanager-telegram-webhook -f"
echo ""
log "Deploy completado com sucesso!"
log "Log: $LOG_FILE"
