#!/usr/bin/env bash
set -euo pipefail

UNIT="mnt-lto6\\x2dsmb\\x2dproof.mount"
MOUNT_POINT="/mnt/lto6-smb-proof"
NAS_IP="192.168.15.4"
LOG="lto6-smb-proof-selfheal"

# Verifica apenas /proc/mounts — não faz syscall de filesystem.
# ls e stat -f bloqueiam quando rsync está escrevendo na fita via CIFS/LTFS,
# gerando falso "stale mount" e SIGKILL no drain (bug 2026-05-15).
# Com opção "soft", o kernel CIFS retorna erros de I/O automaticamente se o
# servidor for genuinamente inacessível — não precisamos testar aqui.
if mountpoint -q "$MOUNT_POINT"; then
    logger -t "$LOG" "mount healthy, nothing to do"
    exit 0
fi

logger -t "$LOG" "mount is down — clearing stale processes"

# Matar drain e rsync que podem estar em D< sobre o mount stale.
# SIGKILL em D< não é processado até o kernel liberar o I/O — por isso
# também reiniciamos smbd na NAS para fechar a TCP e desbloquear o kernel.
pkill -9 -f "lto6-drain-backups" 2>/dev/null || true
pkill -9 -f "rsync.*lto6-smb-proof" 2>/dev/null || true
pkill -9 -f "mount\.cifs.*LTO6_CACHE" 2>/dev/null || true

# Fechar sessão SMB da NAS para desbloquear processos D< no kernel CIFS.
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
       root@"$NAS_IP" "systemctl restart smbd" 2>/dev/null; then
    logger -t "$LOG" "smbd reiniciado na NAS para liberar sessão stale"
else
    logger -t "$LOG" "WARN: não foi possível reiniciar smbd na NAS via SSH"
fi

# Aguardar processos D< serem liberados pelo kernel (até 15s)
for i in $(seq 1 15); do
    if ! pgrep -f "mount\.cifs.*LTO6_CACHE" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

systemctl reset-failed "$UNIT" 2>/dev/null || true
logger -t "$LOG" "remontando $UNIT"
systemctl restart "$UNIT"

# Verificar apenas via /proc/mounts
sleep 5
if mountpoint -q "$MOUNT_POINT"; then
    logger -t "$LOG" "mount restaurado com sucesso"
    systemctl start lto6-drain-backups.service 2>/dev/null && \
        logger -t "$LOG" "drain reiniciado via systemctl" || \
        logger -t "$LOG" "WARN: drain não reiniciado (pode já estar rodando ou sem snapshots)"
else
    logger -t "$LOG" "ERROR: mount não voltou após restart"
    exit 1
fi
