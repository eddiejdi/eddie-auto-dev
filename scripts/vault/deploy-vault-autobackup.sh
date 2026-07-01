#!/bin/bash
# Instala o sistema de auto-backup do vault no notebook local
# Deve ser executado UMA VEZ após vault-setup.sh + vault-add-keyfile.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Execute como root: sudo $0"; exit 1; }

echo "=== DEPLOY VAULT AUTO-BACKUP ==="

# 1. Copiar script de backup para local estável (não depende do path do repo)
echo "[1/4] Instalando script de backup em /opt/homelab/vault/..."
mkdir -p /opt/homelab/vault
cp "$SCRIPT_DIR/backup-to-vault.sh" /opt/homelab/vault/backup-to-vault.sh
chmod +x /opt/homelab/vault/backup-to-vault.sh

# 2. Instalar units systemd
echo "[2/4] Instalando units systemd..."
cp "$REPO_ROOT/systemd/homelab-vault-backup.service" /etc/systemd/system/
cp "$REPO_ROOT/systemd/homelab-vault-close.service" /etc/systemd/system/
systemctl daemon-reload

# 3. Instalar udev rule
echo "[3/4] Instalando udev rule..."
cp "$REPO_ROOT/deploy/99-homelab-vault.rules" /etc/udev/rules.d/
udevadm control --reload-rules

# 4. Verificar keyfile
echo "[4/4] Verificando keyfile LUKS..."
if [ ! -f /etc/homelab-vault.key ]; then
    echo ""
    echo "ATENÇÃO: keyfile não encontrado em /etc/homelab-vault.key"
    echo "Execute primeiro: sudo $SCRIPT_DIR/vault-add-keyfile.sh"
    echo ""
else
    echo "Keyfile OK."
fi

echo ""
echo "=== DEPLOY CONCLUÍDO ==="
echo ""
echo "Comportamento após o deploy:"
echo "  → Inserir pendrive Kingston  : backup inicia automaticamente"
echo "  → Remover pendrive           : vault fecha automaticamente"
echo ""
echo "Monitorar execução:"
echo "  journalctl -fu homelab-vault-backup.service"
echo ""
echo "Testar manualmente:"
echo "  sudo systemctl start homelab-vault-backup.service"
