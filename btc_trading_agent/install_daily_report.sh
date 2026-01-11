#!/bin/bash
# Instalar o timer de relatório diário do Bitcoin Trading Agent

echo "📊 Instalando Bitcoin Daily Report Timer..."

# Diretório base
BASE_DIR="/home/home-lab/myClaude/btc_trading_agent"
SYSTEMD_DIR="/etc/systemd/system"

# Criar diretório de logs se não existir
mkdir -p "$BASE_DIR/logs"

# Copiar arquivos de serviço
echo "📁 Copiando arquivos de serviço..."
sudo cp "$BASE_DIR/btc-daily-report.service" "$SYSTEMD_DIR/"
sudo cp "$BASE_DIR/btc-daily-report.timer" "$SYSTEMD_DIR/"

# Recarregar systemd
echo "🔄 Recarregando systemd..."
sudo systemctl daemon-reload

# Habilitar e iniciar o timer
echo "⏰ Habilitando timer para 6:00 AM..."
sudo systemctl enable btc-daily-report.timer
sudo systemctl start btc-daily-report.timer

# Verificar status
echo ""
echo "📋 Status do timer:"
sudo systemctl status btc-daily-report.timer --no-pager

echo ""
echo "⏱️ Próximas execuções:"
sudo systemctl list-timers btc-daily-report.timer --no-pager

echo ""
echo "✅ Instalação concluída!"
echo ""
echo "Comandos úteis:"
echo "  - Ver status:    sudo systemctl status btc-daily-report.timer"
echo "  - Ver logs:      tail -f $BASE_DIR/logs/daily_report.log"
echo "  - Testar agora:  sudo systemctl start btc-daily-report.service"
echo "  - Parar timer:   sudo systemctl stop btc-daily-report.timer"
