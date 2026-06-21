#!/bin/bash
# Abre ou fecha o vault LUKS do pendrive Kingston
set -euo pipefail

PARTITION="/dev/sda2"
MAPPER_NAME="homelab-vault"
MOUNT_POINT="/mnt/vault"

[ "$(id -u)" -eq 0 ] || { echo "Execute como root: sudo $0 [open|close]"; exit 1; }

case "${1:-open}" in
    open)
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            echo "Vault já está montado em $MOUNT_POINT"
            exit 0
        fi
        if ! lsblk "$PARTITION" &>/dev/null; then
            echo "ERRO: Pendrive não encontrado ($PARTITION). Conecte o dispositivo."
            exit 1
        fi
        echo "Abrindo vault..."
        cryptsetup open "$PARTITION" "$MAPPER_NAME"
        mkdir -p "$MOUNT_POINT"
        mount /dev/mapper/"$MAPPER_NAME" "$MOUNT_POINT"
        echo "Vault montado em $MOUNT_POINT"
        df -h "$MOUNT_POINT"
        ;;
    close)
        echo "Fechando vault..."
        umount "$MOUNT_POINT" 2>/dev/null || true
        cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
        echo "Vault fechado."
        ;;
    status)
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            echo "Vault: ABERTO ($MOUNT_POINT)"
            df -h "$MOUNT_POINT"
        else
            echo "Vault: FECHADO"
        fi
        ;;
    *)
        echo "Uso: $0 [open|close|status]"
        exit 1
        ;;
esac
