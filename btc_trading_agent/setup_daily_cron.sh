#!/bin/bash
# Configurar cron para relatório diário às 6:00 AM

echo "📊 Configurando relatório diário do Bitcoin Trading Agent via cron..."

SCRIPT_PATH="/home/homelab/myClaude/btc_trading_agent/daily_report.py"
LOG_PATH="/home/homelab/myClaude/btc_trading_agent/logs/daily_report.log"

# Criar diretório de logs
mkdir -p /home/homelab/myClaude/btc_trading_agent/logs

# Adicionar ao crontab (6:00 AM todos os dias)
CRON_ENTRY="0 6 * * * /usr/bin/python3 $SCRIPT_PATH >> $LOG_PATH 2>&1"

# Verificar se já existe
if crontab -l 2>/dev/null | grep -q "daily_report.py"; then
    echo "⚠️ Entrada de cron já existe. Removendo antiga..."
    crontab -l | grep -v "daily_report.py" | crontab -
fi

# Adicionar nova entrada
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron configurado para executar às 6:00 AM!"
echo ""
echo "📋 Entrada adicionada:"
echo "   $CRON_ENTRY"
echo ""
echo "📋 Crontab atual:"
crontab -l

echo ""
echo "Comandos úteis:"
echo "  - Ver crontab:    crontab -l"
echo "  - Editar:         crontab -e"
echo "  - Ver logs:       tail -f $LOG_PATH"
echo "  - Testar agora:   python3 $SCRIPT_PATH"
