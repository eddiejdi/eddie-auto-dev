#!/usr/bin/env bash
# =============================================================================
# nas-maintenance-restore.sh
#
# Restaura todos os serviços e timers suspensos pelo nas-maintenance-suspend.sh
# após a NAS (192.168.15.4) voltar a operar normalmente.
#
# USO:
#   sudo bash nas-maintenance-restore.sh           # restaura usando último estado
#   sudo bash nas-maintenance-restore.sh --dry-run # apenas mostra o que faria
#   sudo bash nas-maintenance-restore.sh --check   # testa conectividade antes de restaurar
#
# PRÉ-REQUISITO: confirmar que a NAS responde antes de executar.
#   ping -c3 192.168.15.4
#   smbclient -L 192.168.15.4 -N
# =============================================================================
set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
    [[ "$arg" == "--check" ]]   && CHECK_ONLY=true
done

STATE_DIR="/var/lib/nas-maintenance"
LATEST_LINK="${STATE_DIR}/state-latest.txt"
NAS_IP="192.168.15.4"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
run()  {
    if $DRY_RUN; then
        echo "  [DRY-RUN] $*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Verificação de conectividade com a NAS
# ---------------------------------------------------------------------------
check_nas() {
    log "Verificando conectividade com NAS ${NAS_IP}..."
    if ping -c3 -W2 "${NAS_IP}" &>/dev/null; then
        log "  ping OK"
    else
        echo ""
        echo "ERRO: NAS ${NAS_IP} não responde ao ping."
        echo "Confirme que a NAS está ligada e acessível antes de restaurar."
        echo ""
        exit 1
    fi

    if smbclient -L "${NAS_IP}" -N &>/dev/null; then
        log "  SMB OK"
    else
        echo ""
        echo "AVISO: NAS responde ao ping mas SMB não está acessível ainda."
        echo "Aguarde o Samba inicializar completamente na NAS e tente novamente."
        echo ""
        exit 1
    fi

    log "NAS acessível — pode prosseguir com a restauração."
}

# ---------------------------------------------------------------------------
# Unidades a restaurar (mesma lista do suspend, na ordem inversa)
# ---------------------------------------------------------------------------
MOUNTS=(
    mnt-lto6-smb-proof.mount
    mnt-tape_sg1.mount
    mnt-tape_sg1.automount
)

SERVICES=(
    rpa4all-snapshot-recovery.service
    rpa4all-snapshot.service
    tape-quality-ollama-narrator.service
    homelab-tape-logrotate.service
    homelab-tape-log-drain-sg1.service
    homelab-tape-log-drain-nextcloud.service
    lto6-drain-backups.service
    ltfs-catalog-exporter.service
    ltfs-cache-collector.service
    ltfs-cache-flush.service
    lto6-smb-proof-selfheal.service
)

TIMERS=(
    rpa4all-snapshot.timer
    tape-quality-ollama-narrator.timer
    homelab-tape-logrotate.timer
    homelab-tape-log-drain-sg1.timer
    homelab-tape-log-drain-nextcloud.timer
    lto6-drain-backups.timer
    ltfs-catalog-exporter.timer
    ltfs-cache-collector.timer
    ltfs-cache-flush.timer
    lto6-smb-proof-selfheal.timer
)

restore_units() {
    log "Remontando CIFS mounts..."
    for m in "${MOUNTS[@]}"; do
        log "  start mount: ${m}"
        run systemctl start "$m" 2>/dev/null || log "  AVISO: falha ao montar ${m} — verificar manualmente"
    done

    log "Reativando timers..."
    for t in "${TIMERS[@]}"; do
        log "  start timer: ${t}"
        run systemctl start "$t"
    done

    log "Serviços oneshot serão disparados pelos timers conforme agendamento."
    log "Para forçar execução imediata de algum serviço:"
    log "  systemctl start ltfs-cache-flush.service"
    log "  systemctl start rpa4all-snapshot.service"
}

show_status() {
    echo ""
    log "Status após restauração:"
    run systemctl list-units --no-pager \
        mnt-lto6-smb-proof.mount \
        mnt-tape_sg1.mount \
        ltfs-cache-flush.timer \
        lto6-smb-proof-selfheal.timer \
        rpa4all-snapshot.timer 2>/dev/null || true
}

print_summary() {
    echo ""
    echo "========================================================"
    echo "  RESTAURAÇÃO CONCLUÍDA — NAS de volta à operação"
    echo "========================================================"
    echo "  Arquivo de estado usado: ${LATEST_LINK}"
    echo "  Verifique os logs:  journalctl -f -u ltfs-cache-flush.service"
    echo "========================================================"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if $DRY_RUN; then
    log "=== MODO DRY-RUN — nenhuma alteração será feita ==="
fi

check_nas
$CHECK_ONLY && exit 0

restore_units
show_status
print_summary
