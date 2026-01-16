#!/bin/bash
# Script de instalação do serviço e timer de treinamento Python
# Execute com: sudo bash install_training_service.sh

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   🔧 INSTALANDO SERVIÇO DE TREINAMENTO PYTHON DIÁRIO 🔧      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Este script precisa ser executado como root (sudo)"
    exit 1
fi

# Diretório dos arquivos de serviço
SERVICE_DIR="/etc/systemd/system"
LOG_FILE="/var/log/python-training.log"

echo "📁 Copiando arquivos de serviço..."

# Copiar arquivos de serviço
cp /home/homelab/python-training.service "$SERVICE_DIR/"
cp /home/homelab/python-training.timer "$SERVICE_DIR/"

# Ajustar permissões
chmod 644 "$SERVICE_DIR/python-training.service"
chmod 644 "$SERVICE_DIR/python-training.timer"

echo "✅ Arquivos copiados para $SERVICE_DIR"

# Criar arquivo de log
echo "📝 Criando arquivo de log..."
touch "$LOG_FILE"
chown homelab:homelab "$LOG_FILE"
chmod 644 "$LOG_FILE"
echo "✅ Log criado em $LOG_FILE"

# Garantir que o script de treinamento é executável
echo "🔐 Ajustando permissões do script..."
chmod +x /home/homelab/train_python_docs.sh
echo "✅ Script de treinamento configurado"

# Recarregar systemd
echo "🔄 Recarregando systemd..."
systemctl daemon-reload
echo "✅ Systemd recarregado"

# Habilitar o timer (não o service diretamente)
echo "⏰ Habilitando timer..."
systemctl enable python-training.timer
echo "✅ Timer habilitado"

# Iniciar o timer
echo "▶️  Iniciando timer..."
systemctl start python-training.timer
echo "✅ Timer iniciado"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "✅ INSTALAÇÃO CONCLUÍDA!"
echo ""
echo "📊 Status do Timer:"
systemctl status python-training.timer --no-pager
echo ""
echo "⏰ Próximas execuções:"
systemctl list-timers python-training.timer --no-pager
echo ""
echo "📋 Comandos úteis:"
echo "   • Ver status:    sudo systemctl status python-training.timer"
echo "   • Ver próximas:  systemctl list-timers python-training.timer"
echo "   • Executar agora: sudo systemctl start python-training.service"
echo "   • Ver logs:      sudo journalctl -u python-training.service"
echo "   • Ver log file:  tail -f /var/log/python-training.log"
echo "   • Parar timer:   sudo systemctl stop python-training.timer"
echo "   • Desabilitar:   sudo systemctl disable python-training.timer"
echo ""
echo "📅 O treinamento será executado todos os dias às 01:00 AM"
echo "════════════════════════════════════════════════════════════════"
