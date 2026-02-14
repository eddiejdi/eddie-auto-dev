#!/bin/bash
# Deploy Home Assistant no homelab via Docker
# Uso: bash home_assistant/deploy_ha.sh
set -euo pipefail

HOMELAB="homelab@192.168.15.2"
REMOTE_DIR="/home/homelab/homeassistant"

echo "=== Deploy Home Assistant no Homelab ==="

# 1. Criar diretórios remotos
echo "1/4 Criando diretórios..."
ssh -o ConnectTimeout=5 "$HOMELAB" "mkdir -p $REMOTE_DIR/config"

# 2. Copiar docker-compose.yml
echo "2/4 Copiando docker-compose.yml..."
scp -o ConnectTimeout=5 home_assistant/docker-compose.yml "$HOMELAB:$REMOTE_DIR/docker-compose.yml"

# 3. Iniciar container
echo "3/4 Iniciando Home Assistant..."
ssh -o ConnectTimeout=5 "$HOMELAB" "cd $REMOTE_DIR && docker-compose pull && docker-compose up -d"

# 4. Aguardar startup
echo "4/4 Aguardando Home Assistant iniciar (pode levar 1-2 min)..."
for i in $(seq 1 24); do
    if ssh -o ConnectTimeout=5 "$HOMELAB" "curl -sf http://localhost:8123/api/ >/dev/null 2>&1"; then
        echo "Home Assistant está rodando em http://192.168.15.2:8123"
        echo "Acesse pelo navegador para completar o onboarding."
        exit 0
    fi
    echo "  Aguardando... ($((i*5))s)"
    sleep 5
done

echo "Home Assistant pode estar iniciando ainda. Verifique em http://192.168.15.2:8123"
echo "Logs: ssh $HOMELAB 'cd $REMOTE_DIR && docker compose logs -f'"
