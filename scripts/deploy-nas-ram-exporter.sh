#!/bin/bash
set -euo pipefail

# Deploy do nas-ram-exporter na NAS (192.168.15.4)
# Executa da workstation onde está o repo eddie-auto-dev

NAS_USER="homelab"
NAS_HOST="192.168.15.4"
NAS_PATH="/apps/eddie-auto-dev"

echo "📦 Implantando nas-ram-exporter na NAS..."

# 1. Copia o script Python
echo "→ Copiando nas_ram_exporter.py..."
scp ~/eddie-auto-dev/tools/nas_ram_exporter.py "${NAS_USER}@${NAS_HOST}:${NAS_PATH}/tools/"

# 2. Copia o service file
echo "→ Copiando unit systemd..."
scp ~/eddie-auto-dev/systemd/nas-ram-exporter.service "${NAS_USER}@${NAS_HOST}:/tmp/"

# 3. Move para /etc/systemd/system e recarrega
echo "→ Instalando serviço..."
ssh "${NAS_USER}@${NAS_HOST}" <<'ENDSSH'
sudo mv /tmp/nas-ram-exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
ENDSSH

# 4. Habilita e inicia
echo "→ Habilitando e iniciando..."
ssh "${NAS_USER}@${NAS_HOST}" <<'ENDSSH'
sudo systemctl enable nas-ram-exporter
sudo systemctl restart nas-ram-exporter
ENDSSH

# 5. Verifica status
echo "→ Verificando status..."
ssh "${NAS_USER}@${NAS_HOST}" <<'ENDSSH'
sudo systemctl status nas-ram-exporter --no-pager
ENDSSH

# 6. Testa endpoint localmente na NAS
echo "→ Testando endpoint..."
ssh "${NAS_USER}@${NAS_HOST}" <<'ENDSSH'
curl -s http://127.0.0.1:11447/ram | jq .
ENDSSH

echo ""
echo "✅ Deploy concluído!"
echo "   Para ver logs: ssh homelab@192.168.15.4 'journalctl -u nas-ram-exporter -f'"
