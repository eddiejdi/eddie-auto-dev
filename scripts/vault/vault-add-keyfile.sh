#!/bin/bash
# Adiciona um keyfile ao LUKS para auto-abrir sem senha interativa
# Roda UMA vez após vault-setup.sh
set -euo pipefail

PARTITION="/dev/sda2"
KEYFILE="/etc/homelab-vault.key"

[ "$(id -u)" -eq 0 ] || { echo "Execute como root: sudo $0"; exit 1; }

if ! lsblk "$PARTITION" &>/dev/null; then
    echo "ERRO: Pendrive não encontrado ($PARTITION). Conecte o dispositivo."
    exit 1
fi

if [ -f "$KEYFILE" ]; then
    echo "Keyfile já existe em $KEYFILE"
    read -rp "Sobrescrever? [s/N] " ans
    [[ "$ans" =~ ^[sS]$ ]] || { echo "Abortado."; exit 0; }
fi

echo "Gerando keyfile em $KEYFILE..."
dd if=/dev/urandom bs=512 count=4 of="$KEYFILE" status=none
chmod 400 "$KEYFILE"

echo "Adicionando keyfile ao LUKS (você precisará digitar a senha do vault)..."
cryptsetup luksAddKey "$PARTITION" "$KEYFILE"

echo ""
echo "Keyfile adicionado com sucesso."
echo "O systemd abrirá o vault automaticamente ao inserir o pendrive."
echo ""
echo "Para remover o keyfile depois (ex: pendrive perdido):"
echo "  sudo cryptsetup luksRemoveKey $PARTITION $KEYFILE"
echo "  sudo rm $KEYFILE"
