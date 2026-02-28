#!/bin/bash
# Ollama Frozen Detection & Recovery Script
# Monitora congelamento do Ollama e executa auto-recuperação

set -euo pipefail

OLLAMA_HOST=${OLLAMA_HOST:-"http://192.168.15.2:11434"}
OLLAMA_SERVICE=${OLLAMA_SERVICE:-"ollama"}
FROZEN_THRESHOLD_SECONDS=${1:-180}
CHECK_INTERVAL=${2:-15}
MAX_RESTARTS_PER_HOUR=${3:-3}
COOLDOWN_SECONDS=${4:-60}

LOG_FILE="/var/log/ollama-selfheal.log"
RESTART_COUNT_FILE="/tmp/ollama_restarts.txt"
LAST_CHECK_FILE="/tmp/ollama_last_check.txt"
STATE_FILE="/tmp/ollama_state.json"

# Inicializar arquivos
touch "$RESTART_COUNT_FILE" "$LAST_CHECK_FILE" 2>/dev/null || true
[ -f "$RESTART_COUNT_FILE" ] || echo "0" > "$RESTART_COUNT_FILE"
[ -f "$LAST_CHECK_FILE" ] || echo "0" > "$LAST_CHECK_FILE"
[ -f "$STATE_FILE" ] || echo '{"status":"unknown"}' > "$STATE_FILE"

log_message() {
    local level=$1
    local msg=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $msg" | tee -a "$LOG_FILE"
}

update_prometheus_metrics() {
    local status=$1
    local frozen_duration=$2
    local restart_count=$3
    
    # Exportar para arquivo que será lido pelo Prometheus
    cat > /tmp/ollama_metrics.txt << EOF
# Ollama Monitoring Metrics
# HELP ollama_up Ollama server status (1=up, 0=down)
# TYPE ollama_up gauge
ollama_up $status

# HELP ollama_frozen_duration_seconds Tempo desde último request bem-sucedido
# TYPE ollama_frozen_duration_seconds gauge
ollama_frozen_duration_seconds $frozen_duration

# HELP ollama_selfheal_restarts_total Total de restarts automáticos
# TYPE ollama_selfheal_restarts_total counter
ollama_selfheal_restarts_total $restart_count

# HELP ollama_last_restart_timestamp Unix timestamp do último restart
# TYPE ollama_last_restart_timestamp gauge
ollama_last_restart_timestamp $(date +%s)
EOF
    
    # Se houver prometheus textfile collector, copiar
    if [ -d "/var/lib/node_exporter/textfile_collector" ]; then
        cp /tmp/ollama_metrics.txt /var/lib/node_exporter/textfile_collector/ollama.prom
    fi
}

check_ollama_responsive() {
    local response
    response=$(timeout 5 curl -s --max-time 3 "$OLLAMA_HOST/api/tags" 2>&1)
    
    if [ $? -eq 0 ] && echo "$response" | grep -q "models"; then
        return 0  # Responsivo
    fi
    return 1  # Não responsivo/congelado
}

get_gpu_utilization() {
    # Tenta coletar via nvidia-smi se disponível
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1
    else
        echo "0"
    fi
}

detect_frozen_state() {
    local last_check=$(cat "$LAST_CHECK_FILE")
    local current_time=$(date +%s)
    local frozen_duration=$((current_time - last_check))
    
    # Verificar se Ollama está congelado
    if ! check_ollama_responsive; then
        # Verificar GPU utilização
        local gpu_util=$(get_gpu_utilization)
        
        if [ "$frozen_duration" -gt "$FROZEN_THRESHOLD_SECONDS" ] && [ "$gpu_util" -lt "5" ]; then
            log_message "CRITICAL" "Ollama CONGELADO por ${frozen_duration}s (GPU: ${gpu_util}%)"
            update_prometheus_metrics 0 "$frozen_duration" "$(cat "$RESTART_COUNT_FILE")"
            return 0  # Congelado
        fi
    else
        # Atualizar last check
        echo "$current_time" > "$LAST_CHECK_FILE"
        update_prometheus_metrics 1 0 0
        return 1  # Responsivo
    fi
    
    return 1  # Indeterminado
}

perform_restart() {
    local restart_count=$(cat "$RESTART_COUNT_FILE")
    
    if [ "$restart_count" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
        log_message "CRITICAL" "Limite de restarts/hora (${MAX_RESTARTS_PER_HOUR}) atingido!"
        return 1
    fi
    
    log_message "INFO" "Iniciando restart de Ollama..."
    
    # Tentar reiniciar
    if ssh homelab@192.168.15.2 "sudo systemctl restart $OLLAMA_SERVICE" 2>&1; then
        log_message "SUCCESS" "Restart de Ollama bem-sucedido"
        
        # Incrementar contador
        echo $((restart_count + 1)) > "$RESTART_COUNT_FILE"
        
        # Resetar contador a cada hora
        (sleep 3600 && echo "0" > "$RESTART_COUNT_FILE") &
        
        # Aguardar Ollama voltar online
        sleep "$COOLDOWN_SECONDS"
        
        # Verificar se voltou
        if check_ollama_responsive; then
            log_message "SUCCESS" "Ollama recuperado e respondendo normalmente"
            echo "$(date +%s)" > "$LAST_CHECK_FILE"
            update_prometheus_metrics 1 0 "$(cat "$RESTART_COUNT_FILE")"
            return 0
        else
            log_message "ERROR" "Ollama ainda não responde após restart"
            return 1
        fi
    else
        log_message "ERROR" "Falha ao executar restart de Ollama"
        return 1
    fi
}

monitor_ollama() {
    log_message "INFO" "Iniciando monitoramento de congelamento do Ollama (threshold: ${FROZEN_THRESHOLD_SECONDS}s)"
    
    while true; do
        if detect_frozen_state; then
            # Ollama congelado detectado
            if ! perform_restart; then
                log_message "CRITICAL" "Falha na auto-recuperação, escalando para admin"
                # Aqui poderia enviar notificação/alerta
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Modo de teste
if [ "${1:-}" = "--test" ]; then
    log_message "INFO" "Modo TESTE ativado"
    check_ollama_responsive && echo "✅ Ollama responsivo" || echo "❌ Ollama congelado"
    echo "GPU: $(get_gpu_utilization)%"
    exit 0
fi

# Modo de limpeza
if [ "${1:-}" = "--reset" ]; then
    echo "0" > "$RESTART_COUNT_FILE"
    echo "0" > "$LAST_CHECK_FILE"
    echo "$(date +%s)" > "$LAST_CHECK_FILE"
    log_message "INFO" "Contadores resetados"
    exit 0
fi

# Modo normal: monitoramento contínuo
monitor_ollama
