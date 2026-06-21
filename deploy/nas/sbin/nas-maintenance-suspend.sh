#!/usr/bin/env bash
# =============================================================================
# nas-maintenance-suspend.sh
#
# Suspende todos os serviços e timers do homelab que dependem da NAS
# (192.168.15.4) durante períodos de manutenção / hardware offline.
#
# CONTEXTO: A NAS teve falha de hardware em 2026-06-06. Todos os mounts CIFS
# apontando para 192.168.15.4 falham com EHOSTUNREACH (-113), causando retry
# storm nos logs e falhas em cascata no pipeline LTO/LTFS.
#
# USO:
#   sudo bash nas-maintenance-suspend.sh           # suspende e salva estado
#   sudo bash nas-maintenance-suspend.sh --dry-run # apenas mostra o que faria
#
# ROLLBACK:
#   sudo bash nas-maintenance-restore.sh
#
# O estado antes da suspensão é salvo em:
#   /var/lib/nas-maintenance/state-<TIMESTAMP>.txt
# =============================================================================
set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

STATE_DIR="/var/lib/nas-maintenance"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
STATE_FILE="${STATE_DIR}/state-${TIMESTAMP}.txt"
LATEST_LINK="${STATE_DIR}/state-latest.txt"

# ---------------------------------------------------------------------------
# Serviços / mounts / timers a suspender (dependentes da NAS 192.168.15.4)
# ---------------------------------------------------------------------------

# Timers — parar primeiro para não disparar novos jobs enquanto suspende
TIMERS=(
    lto6-smb-proof-selfheal.timer   # tenta remount do CIFS gate a cada 2 min
    ltfs-cache-flush.timer          # flush de cache LTO para LTFS via CIFS
    ltfs-cache-collector.timer      # coleta métricas de cache via SSH na NAS
    ltfs-catalog-exporter.timer     # exporta catálogo LTFS para Prometheus
    lto6-drain-backups.timer        # drain diário de snapshots para fita LTO
    homelab-tape-log-drain-nextcloud.timer
    homelab-tape-log-drain-sg1.timer
    homelab-tape-logrotate.timer
    tape-quality-ollama-narrator.timer
    rpa4all-snapshot.timer          # snapshot diário do Nextcloud
)

# Serviços ativos que devem ser parados
SERVICES=(
    lto6-smb-proof-selfheal.service
    ltfs-cache-flush.service
    ltfs-cache-collector.service
    ltfs-catalog-exporter.service
    lto6-drain-backups.service
    homelab-tape-log-drain-nextcloud.service
    homelab-tape-log-drain-sg1.service
    homelab-tape-logrotate.service
    tape-quality-ollama-narrator.service
    rpa4all-snapshot.service
    rpa4all-snapshot-recovery.service
)

# Mounts CIFS que apontam para a NAS
MOUNTS=(
    mnt-lto6-smb-proof.mount    # gate de reachability da NAS
    mnt-tape_sg1.mount          # export CIFS do LTFS SG1
    mnt-tape_sg1.automount      # automount associado ao SG1
)

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
run()  {
    if $DRY_RUN; then
        echo "  [DRY-RUN] $*"
    else
        "$@"
    fi
}

capture_state() {
    log "Capturando estado atual em ${STATE_FILE}..."
    run mkdir -p "${STATE_DIR}"
    if ! $DRY_RUN; then
        {
            echo "# Estado capturado em ${TIMESTAMP}"
            echo "# NAS offline por manutenção de hardware (queima 2026-06-06)"
            echo ""
            echo "## Timers"
            for t in "${TIMERS[@]}"; do
                state=$(systemctl is-active "$t" 2>/dev/null || echo "inactive")
                enabled=$(systemctl is-enabled "$t" 2>/dev/null || echo "disabled")
                echo "TIMER ${t} active=${state} enabled=${enabled}"
            done
            echo ""
            echo "## Services"
            for s in "${SERVICES[@]}"; do
                state=$(systemctl is-active "$s" 2>/dev/null || echo "inactive")
                enabled=$(systemctl is-enabled "$s" 2>/dev/null || echo "disabled")
                echo "SERVICE ${s} active=${state} enabled=${enabled}"
            done
            echo ""
            echo "## Mounts"
            for m in "${MOUNTS[@]}"; do
                state=$(systemctl is-active "$m" 2>/dev/null || echo "inactive")
                echo "MOUNT ${m} active=${state}"
            done
        } > "${STATE_FILE}"
        ln -sf "${STATE_FILE}" "${LATEST_LINK}"
        log "Estado salvo em ${STATE_FILE}"
    fi
}

stop_units() {
    log "Parando timers..."
    for t in "${TIMERS[@]}"; do
        if systemctl is-active --quiet "$t" 2>/dev/null; then
            log "  stop timer: ${t}"
            run systemctl stop "$t"
        else
            log "  já inativo: ${t}"
        fi
    done

    log "Parando serviços..."
    for s in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$s" 2>/dev/null || \
           [[ "$(systemctl is-active "$s" 2>/dev/null)" == "activating" ]]; then
            log "  stop service: ${s}"
            run systemctl stop "$s" 2>/dev/null || true
        else
            log "  já inativo: ${s}"
        fi
    done

    log "Desmontando CIFS mounts..."
    for m in "${MOUNTS[@]}"; do
        active=$(systemctl is-active "$m" 2>/dev/null || echo "inactive")
        if [[ "$active" != "inactive" && "$active" != "dead" ]]; then
            log "  stop mount: ${m}"
            run systemctl stop "$m" 2>/dev/null || true
        else
            log "  já inativo: ${m}"
        fi
    done
}

print_summary() {
    echo ""
    echo "========================================================"
    echo "  SUSPENSÃO CONCLUÍDA — NAS em manutenção"
    echo "========================================================"
    echo "  Estado salvo em: ${LATEST_LINK}"
    echo "  Para restaurar:  sudo bash nas-maintenance-restore.sh"
    echo "========================================================"
    echo ""
    echo "Serviços que continuam rodando normalmente (locais):"
    echo "  mnt-lto6.mount, mnt-lto6-nc.mount, mnt-tape_sg0.mount"
    echo "  rpa4all-snapshot-exporter.service (Prometheus exporter)"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if $DRY_RUN; then
    log "=== MODO DRY-RUN — nenhuma alteração será feita ==="
fi

capture_state
stop_units
print_summary
