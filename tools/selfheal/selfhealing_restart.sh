#!/bin/bash
# Self-Healing Auto-Restart Script
# Acionado por alertas do Prometheus quando stall > 300s é detectado

set -euo pipefail

SERVICE=$1
STALL_THRESHOLD_SECONDS=${2:-300}
MAX_RESTARTS_PER_HOUR=${3:-3}
COOLDOWN_SECONDS=${4:-60}

LOG_FILE="/var/log/eddie-selfheal.log"
RESTART_COUNT_FILE="/tmp/selfheal_restarts_${SERVICE}.txt"

# Inicializar arquivo de contagem
if [ ! -f "$RESTART_COUNT_FILE" ]; then
    echo "0" > "$RESTART_COUNT_FILE"
fi

log_message() {
    local level=$1
    local msg=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] [$SERVICE] $msg" | tee -a "$LOG_FILE"
}

check_restart_limit() {
    local current_count=$(cat "$RESTART_COUNT_FILE")
    if [ "$current_count" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
        log_message "CRITICAL" "Limite de restarts/hora (${MAX_RESTARTS_PER_HOUR}) atingido!"
        return 1
    fi
    return 0
}

perform_restart() {
    log_message "INFO" "Iniciando restart automático para $SERVICE"
    
    if systemctl restart "$SERVICE" 2>&1; then
        log_message "SUCCESS" "Restart de $SERVICE bem-sucedido"
        
        # Atualizar contador
        local current_count=$(cat "$RESTART_COUNT_FILE")
        echo $((current_count + 1)) > "$RESTART_COUNT_FILE"
        
        # Resetar contador a cada hora
        (sleep 3600 && echo "0" > "$RESTART_COUNT_FILE") &
        
        sleep "$COOLDOWN_SECONDS"
        return 0
    else
        log_message "ERROR" "Falha ao reiniciar $SERVICE"
        return 1
    fi
}

main() {
    log_message "INFO" "Self-healing iniciado para $SERVICE (stall_threshold=${STALL_THRESHOLD_SECONDS}s)"
    
    # Verificar saúde do serviço
    if ! systemctl is-active --quiet "$SERVICE"; then
        log_message "WARN" "$SERVICE não está ativo, tentando reiniciar..."
        if check_restart_limit; then
            perform_restart
        else
            log_message "CRITICAL" "Restart bloqueado: limite de tentativas atingido"
            exit 1
        fi
    else
        log_message "INFO" "$SERVICE está ativo, aguardando próxima verificação"
    fi
}

main "$@"
