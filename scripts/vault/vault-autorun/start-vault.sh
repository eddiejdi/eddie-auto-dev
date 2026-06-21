#!/bin/bash
# Homelab Vault — Linux launcher (para uso manual sem systemd)
set -euo pipefail

VAULT_MOUNT="/mnt/vault"
PARTITION="/dev/sda1"
MAPPER="homelab-vault"
KEYFILE="/etc/homelab-vault.key"
SERVER_SCRIPT="/opt/homelab/vault/vault-server.py"
PORT=8765

# Montar vault se necessário
if ! mountpoint -q "$VAULT_MOUNT" 2>/dev/null; then
    echo "Abrindo vault..."
    if [ -f "$KEYFILE" ]; then
        sudo cryptsetup open --key-file "$KEYFILE" "$PARTITION" "$MAPPER"
    else
        sudo cryptsetup open "$PARTITION" "$MAPPER"
    fi
    sudo mkdir -p "$VAULT_MOUNT"
    sudo mount /dev/mapper/"$MAPPER" "$VAULT_MOUNT"
fi

# Verificar se servidor já está rodando
if curl -s "http://localhost:$PORT/api/status" &>/dev/null; then
    echo "Servidor já rodando — abrindo navegador..."
    xdg-open "http://localhost:$PORT" 2>/dev/null || \
    python3 -m webbrowser "http://localhost:$PORT"
    exit 0
fi

# Iniciar servidor
echo "Iniciando Vault UI em http://localhost:$PORT ..."
sudo python3 "$SERVER_SCRIPT" &
SRV_PID=$!

# Aguardar até 10s
for i in $(seq 1 10); do
    sleep 1
    curl -s "http://localhost:$PORT/api/status" &>/dev/null && break
done

xdg-open "http://localhost:$PORT" 2>/dev/null || \
python3 -m webbrowser "http://localhost:$PORT" || \
echo "Abra manualmente: http://localhost:$PORT"

echo "Servidor PID: $SRV_PID — Ctrl+C para encerrar"
wait "$SRV_PID"
