#!/usr/bin/env bash
set -euo pipefail

echo "Instalando Secrets Agent..."
sudo mkdir -p /var/lib/eddie/secrets_agent
sudo chown -R $(whoami):$(whoami) /var/lib/eddie/secrets_agent

# copy unit
sudo cp tools/secrets_agent/secrets_agent.service /etc/systemd/system/secrets_agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now secrets_agent.service

echo "Secrets Agent instalado e iniciado. Expondo métricas em porta 8001 e API em 8088 por padrão."
echo "Defina SECRETS_AGENT_API_KEY no unit file ou em /etc/systemd/system/secrets_agent.service.d/override.conf"
