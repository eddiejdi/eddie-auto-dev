#!/bin/bash
# Configuração única: cria 2 partições no pendrive Kingston
#   sda1 — FAT32 512MB  "VAULT-START"  (launchers, autorun — visível no Windows)
#   sda2 — LUKS2 resto  "homelab-vault" (dados cifrados)
# AVISO: apaga todos os dados em /dev/sda
set -euo pipefail

DEVICE="/dev/sda"
BOOT_PART="${DEVICE}1"
LUKS_PART="${DEVICE}2"
MAPPER_NAME="homelab-vault"
VAULT_MOUNT="/mnt/vault"
BOOT_MOUNT="/mnt/vault-boot"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Execute como root: sudo $0"; exit 1; }

if ! lsblk "$DEVICE" &>/dev/null; then
    echo "ERRO: Dispositivo $DEVICE não encontrado."
    exit 1
fi

echo "=== CONFIGURAÇÃO DO VAULT LUKS ==="
echo ""
echo "Dispositivo: $DEVICE"
lsblk -o NAME,SIZE,MODEL,LABEL "$DEVICE"
echo ""
echo "Layout que será criado:"
echo "  ${DEVICE}1  FAT32  512MB  — launchers (visível no Windows/Mac)"
echo "  ${DEVICE}2  LUKS2  resto  — vault cifrado"
echo ""
echo "ATENÇÃO: TODOS os dados em $DEVICE serão APAGADOS permanentemente."
echo ""
read -rp "Digite 'CONFIRMO' para continuar: " confirm
[ "$confirm" = "CONFIRMO" ] || { echo "Abortado."; exit 1; }

# Desmontar tudo
echo ""
echo "[1/6] Desmontando e limpando..."
for i in 1 2; do
    umount "${DEVICE}${i}" 2>/dev/null || true
done
cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
wipefs -a "$DEVICE"

# Particionamento
echo "[2/6] Criando partições..."
parted -s "$DEVICE" mklabel gpt
parted -s "$DEVICE" mkpart "VAULT-START" fat32 1MiB 513MiB
parted -s "$DEVICE" mkpart "vault-luks"        513MiB 100%
partprobe "$DEVICE"
sleep 2

# FAT32 na partição de boot
echo "[3/6] Formatando partição FAT32..."
mkfs.fat -F32 -n "VAULT-START" "$BOOT_PART"

# LUKS2 na partição de dados
echo ""
echo "[4/6] Criando container LUKS2 (defina uma senha forte)..."
cryptsetup luksFormat --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha256 \
    --iter-time 5000 \
    "$LUKS_PART"

echo "[5/6] Formatando vault interno..."
cryptsetup open "$LUKS_PART" "$MAPPER_NAME"
mkfs.ext4 -L homelab-vault /dev/mapper/"$MAPPER_NAME"

# Estrutura do vault
mkdir -p "$VAULT_MOUNT"
mount /dev/mapper/"$MAPPER_NAME" "$VAULT_MOUNT"
mkdir -p "$VAULT_MOUNT/keepass" \
         "$VAULT_MOUNT/keys/storj/wallet" \
         "$VAULT_MOUNT/keys/storj/identity" \
         "$VAULT_MOUNT/backups/authentik" \
         "$VAULT_MOUNT/backups/vaultwarden" \
         "$VAULT_MOUNT/backups/bitwarden-cloud" \
         "$VAULT_MOUNT/backups/storj" \
         "$VAULT_MOUNT/ui"
chmod 700 "$VAULT_MOUNT"/{keepass,keys}
chmod 700 "$VAULT_MOUNT/keys/storj" "$VAULT_MOUNT/keys/storj/wallet" "$VAULT_MOUNT/keys/storj/identity"
chmod 750 "$VAULT_MOUNT"/backups

# Copiar vault-server.py e index.html para dentro do vault
cp "$SCRIPT_DIR/vault-server.py" "$VAULT_MOUNT/"
cp "$SCRIPT_DIR/vault-ui/index.html" "$VAULT_MOUNT/ui/"
umount "$VAULT_MOUNT"
cryptsetup close "$MAPPER_NAME"

# Partição FAT32 — copiar launchers
echo "[6/6] Instalando launchers na partição FAT32..."
mkdir -p "$BOOT_MOUNT"
mount "$BOOT_PART" "$BOOT_MOUNT"

cp "$SCRIPT_DIR/vault-autorun/autorun.inf"               "$BOOT_MOUNT/"
cp "$SCRIPT_DIR/vault-autorun/Start Vault.bat"           "$BOOT_MOUNT/"
cp "$SCRIPT_DIR/vault-autorun/start-vault.sh"            "$BOOT_MOUNT/"
cp "$SCRIPT_DIR/vault-server.py"                         "$BOOT_MOUNT/"
# Instalador Windows
mkdir -p "$BOOT_MOUNT/Install Windows"
cp "$SCRIPT_DIR/install-windows/Install Vault Windows.bat" "$BOOT_MOUNT/Install Windows/"
cp "$SCRIPT_DIR/install-windows/install-vault.ps1"         "$BOOT_MOUNT/Install Windows/"
cp "$SCRIPT_DIR/install-windows/vault-monitor.ps1"         "$BOOT_MOUNT/Install Windows/"

# README para Windows
cat > "$BOOT_MOUNT/LEIA-ME.txt" << 'EOF'
=== HOMELAB VAULT ===

Linux (automático):
  Insira o pendrive — o painel abre automaticamente em http://localhost:8765

Linux (manual):
  bash start-vault.sh

Windows (primeira vez — instalar uma vez):
  1. Abra a pasta "Install Windows" no pendrive
  2. Clique com botão direito em "Install Vault Windows.bat" → Executar como Admin
  3. Siga as instruções (instala Python, monitor USB e atalho na área de trabalho)

Windows (uso diário após instalação):
  1. Insira o pendrive
  2. Abra a partição LUKS com LibreCrypt (https://github.com/t-d-k/LibreCrypt)
  3. Navegador abre automaticamente em http://localhost:8765

Login padrão: admin / admin
EOF

chmod +x "$BOOT_MOUNT/start-vault.sh"
umount "$BOOT_MOUNT"
rmdir "$BOOT_MOUNT"

echo ""
echo "=== VAULT CRIADO COM SUCESSO ==="
echo ""
echo "Partições:"
lsblk -o NAME,SIZE,FSTYPE,LABEL "$DEVICE"
echo ""
echo "Próximos passos:"
echo "  1. sudo ./vault-add-keyfile.sh        — adicionar keyfile para auto-abrir"
echo "  2. sudo ./deploy-vault-autobackup.sh  — instalar systemd + udev"
echo "  3. Remova e reinsira o pendrive para testar o autorun"
