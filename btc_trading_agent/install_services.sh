#!/bin/bash

echo "🔧 Instalando serviços do Bitcoin Trading Agent..."

# Criar versões corrigidas dos serviços
for service in btc-trading-engine.service btc-daily-report.service btc-webui-api.service; do
    if [ -f "$service" ]; then
        sed 's/homelab/eddie/g' "$service" > "/tmp/$service"
        sudo cp "/tmp/$service" "/etc/systemd/system/$service"
        echo "✅ $service instalado"
    fi
done

# Instalar timer se existir
if [ -f "btc-daily-report.timer" ]; then
    sed 's/homelab/eddie/g' btc-daily-report.timer > /tmp/btc-daily-report.timer
    sudo cp /tmp/btc-daily-report.timer /etc/systemd/system/btc-daily-report.timer
    echo "✅ btc-daily-report.timer instalado"
fi

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar e iniciar serviços
echo "🚀 Habilitando e iniciando serviços..."
sudo systemctl enable btc-engine-api.service
sudo systemctl enable btc-trading-engine.service
sudo systemctl enable btc-daily-report.service
sudo systemctl enable btc-webui-api.service
sudo systemctl enable btc-daily-report.timer

# Iniciar serviços
sudo systemctl start btc-trading-engine.service
sudo systemctl start btc-daily-report.service
sudo systemctl start btc-webui-api.service

echo "✅ Serviços instalados e iniciados!"
echo ""
echo "📊 Status dos serviços:"
systemctl list-units --type=service --state=active | grep btc
systemctl list-units --type=timer --state=active | grep btc

echo ""
echo "🔍 Para verificar logs:"
echo "  journalctl -u btc-trading-engine.service -f"
echo "  journalctl -u btc-engine-api.service -f" 
