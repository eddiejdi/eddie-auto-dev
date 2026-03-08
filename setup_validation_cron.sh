#!/bin/bash
# Setup de Cron Job para Validações Periódicas
# Executa validação Selenium diariamente em horários configuráveis

set -e

PROJECT_DIR="/home/edenilson/shared-auto-dev"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python3"
LOG_DIR="/var/log/rpa4all-validation"
CRON_SCHEDULE="${1:-0 2 * * *}"  # Padrão: 2 AM diariamente

echo "🔧 Setup de Cron Job para Validações"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Criar diretório de logs
sudo mkdir -p "$LOG_DIR"
sudo chown $USER:$USER "$LOG_DIR"
chmod 755 "$LOG_DIR"
echo "✅ Diretório de logs criado: $LOG_DIR"

# Criar script de wrapper
CRON_SCRIPT="/usr/local/bin/validate-landing-pages"
sudo tee "$CRON_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash
# Wrapper para execução de validação via cron

VENV_PYTHON="/home/edenilson/shared-auto-dev/.venv/bin/python3"
SCHEDULER="/home/edenilson/shared-auto-dev/validation_scheduler.py"
LOG_FILE="/var/log/rpa4all-validation/validation_$(date +%Y-%m-%d_%H-%M-%S).log"

# Executar validação
"$VENV_PYTHON" "$SCHEDULER" "https://www.rpa4all.com/" >> "$LOG_FILE" 2>&1

# Manter apenas últimos 30 dias de logs
find /var/log/rpa4all-validation -name "validation_*.log" -mtime +30 -delete
EOF

sudo chmod +x "$CRON_SCRIPT"
echo "✅ Script cron criado: $CRON_SCRIPT"

# Instalar no crontab
echo ""
echo "📋 Cron Schedule: $CRON_SCHEDULE"
echo "   (Padrão: 0 2 * * * = 2 AM diariamente)"
echo ""
echo "Exemplos de schedule:"
echo "   0 2 * * *     - Todo dia às 2 AM"
echo "   0 */6 * * *   - A cada 6 horas"
echo "   */30 * * * *  - A cada 30 minutos"
echo ""

# Verificar se job já existe
if crontab -l 2>/dev/null | grep -q "validate-landing-pages"; then
    echo "⚠️  Cron job já existe. Removendo versão anterior..."
    (crontab -l 2>/dev/null | grep -v "validate-landing-pages" || true) | crontab -
fi

# Instalar novo job
(crontab -l 2>/dev/null || echo "") | {
    cat
    echo "$CRON_SCHEDULE $CRON_SCRIPT  # RPA4ALL Landing Page Validation"
} | crontab -

echo "✅ Cron job instalado!"
echo ""
echo "📊 Verificar logs:"
echo "   tail -f /var/log/rpa4all-validation/validation_*.log"
echo ""
echo "📋 Listar cron jobs:"
echo "   crontab -l"
echo ""
echo "🗑️  Remover cron job:"
echo "   crontab -l | grep -v 'validate-landing-pages' | crontab -"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup concluído!"
