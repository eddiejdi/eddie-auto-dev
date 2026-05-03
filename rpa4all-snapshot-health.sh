#!/bin/bash
# Health check para rpa4all-snapshot
# Verifica se o processo está travado e reinicia se necessário

set -euo pipefail

LOCK_FILE="/tmp/rpa4all-snapshot.lock"
MAX_AGE_SECS=1800  # 30 minutos — tempo máximo aceitável

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a /var/log/rpa4all-snapshot-health.log
}

# Verificar se há um processo em execução
check_process() {
    if systemctl is-active --quiet rpa4all-snapshot.service; then
        log "✓ Serviço rodando normalmente"
        return 0
    fi
    
    # Verificar lock file (indica que estava rodando antes)
    if [[ -f "$LOCK_FILE" ]]; then
        LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
        
        if [[ $LOCK_AGE -gt $MAX_AGE_SECS ]]; then
            log "⚠ TRAVAMENTO DETECTADO! Lock file com ${LOCK_AGE}s (limite: ${MAX_AGE_SECS}s)"
            log "Reiniciando serviço..."
            systemctl restart rpa4all-snapshot.service
            return 1
        else
            log "✓ Serviço parado normalmente (${LOCK_AGE}s desde último lock)"
            rm -f "$LOCK_FILE"
            return 0
        fi
    fi
    
    return 0
}

check_process
