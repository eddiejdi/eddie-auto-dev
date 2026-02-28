#!/bin/bash
# Prometheus Ollama Metrics Exporter
# Coleta métricas do Ollama via API e expõe para Prometheus
# Destino: /var/lib/node_exporter/textfile_collector/ollama.prom

set -euo pipefail

OLLAMA_HOST=${OLLAMA_HOST:-"http://192.168.15.2:11434"}
METRICS_FILE="/tmp/ollama_metrics.prom"
LAST_RESPONSE_FILE="/tmp/ollama_last_response.txt"

# Inicializar arquivo de última resposta
touch "$LAST_RESPONSE_FILE"
LAST_RESPONSE=$(cat "$LAST_RESPONSE_FILE" 2>/dev/null || echo "$(date +%s)")

export_metric() {
    local name=$1
    local type=$2
    local help=$3
    local value=$4
    local labels=${5:-}
    
    {
        echo "# HELP $name $help"
        echo "# TYPE $name $type"
        if [ -n "$labels" ]; then
            echo "${name}${labels} $value"
        else
            echo "$name $value"
        fi
    } >> "$METRICS_FILE"
}

collect_ollama_metrics() {
    > "$METRICS_FILE"
    
    local current_time=$(date +%s)
    
    # 1. Status (up/down)
    local ollama_up=0
    if curl -sf --max-time 2 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        ollama_up=1
        echo "$current_time" > "$LAST_RESPONSE_FILE"
    fi
    
    export_metric "ollama_up" "gauge" "Ollama server is reachable" "$ollama_up"
    
    # 2. Tempo desde última resposta (para detectar congelamento)
    local last_response=$(cat "$LAST_RESPONSE_FILE")
    local frozen_duration=$((current_time - last_response))
    export_metric "ollama_last_request_timestamp" "gauge" "Unix timestamp of last successful request" "$last_response"
    export_metric "ollama_frozen_duration_seconds" "gauge" "Seconds since last successful request" "$frozen_duration"
    
    # 3. Modelos carregados
    local tags_response
    tags_response=$(curl -s --max-time 3 "$OLLAMA_HOST/api/tags" 2>/dev/null || echo "")
    
    if [ -n "$tags_response" ]; then
        local model_count=$(echo "$tags_response" | jq -r '.models | length' 2>/dev/null || echo "0")
        export_metric "ollama_models_loaded" "gauge" "Number of models currently loaded" "$model_count"
        
        # Tamanho total dos modelos
        local total_size=$(echo "$tags_response" | jq -r '[.models[].size] | add' 2>/dev/null || echo "0")
        export_metric "ollama_models_total_size_bytes" "gauge" "Total size of all loaded models" "$total_size"
    fi
    
    # 4. Modelos ativos (models ps endpoint)
    local ps_response
    ps_response=$(curl -s --max-time 3 "$OLLAMA_HOST/api/ps" 2>/dev/null || echo "")
    
    if [ -n "$ps_response" ]; then
        local active_models=$(echo "$ps_response" | jq -r '.models | length' 2>/dev/null || echo "0")
        export_metric "ollama_models_active" "gauge" "Number of currently active models" "$active_models"
        
        # Memória VRAM usada por modelos ativos
        local vram_used=$(echo "$ps_response" | jq -r '[.models[].size_vram] | add // 0' 2>/dev/null || echo "0")
        export_metric "ollama_vram_used_bytes" "gauge" "VRAM used by active models" "$vram_used"
    fi
    
    # 5. GPU info (se nvidia-smi disponível)
    if command -v nvidia-smi &> /dev/null; then
        local gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        local gpu_mem_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
        local gpu_mem_total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        local gpu_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        
        gpu_util=${gpu_util:-0}
        gpu_mem_used=${gpu_mem_used:-0}
        gpu_mem_total=${gpu_mem_total:-8192}
        gpu_temp=${gpu_temp:-0}
        
        # Converter para bytes (nvidia retorna em MB)
        gpu_mem_used=$((gpu_mem_used * 1048576))
        gpu_mem_total=$((gpu_mem_total * 1048576))
        
        export_metric "ollama_gpu_utilization_percent" "gauge" "GPU utilization percentage" "$gpu_util"
        export_metric "ollama_gpu_memory_used_bytes" "gauge" "GPU memory used in bytes" "$gpu_mem_used"
        export_metric "ollama_gpu_memory_total_bytes" "gauge" "GPU memory total in bytes" "$gpu_mem_total"
        export_metric "ollama_gpu_temperature_celsius" "gauge" "GPU temperature in Celsius" "$gpu_temp"
    fi
    
    # 6. Métricas de congelamento (se o daemon de monitoramento está rodando)
    if [ -f "/tmp/ollama_metrics.txt" ]; then
        cat "/tmp/ollama_metrics.txt" >> "$METRICS_FILE"
    fi
    
    # Copiar para node_exporter textfile collector se existir
    if [ -d "/var/lib/node_exporter/textfile_collector" ] 2>/dev/null; then
        cp "$METRICS_FILE" "/var/lib/node_exporter/textfile_collector/ollama.prom" 2>/dev/null || true
    fi
}

# Executar coleta
collect_ollama_metrics

# Modo contínuo (se chamado com --daemon)
if [ "${1:-}" = "--daemon" ]; then
    interval="${2:-15}"
    echo "Ollama metrics collector running (interval: ${interval}s)"
    while true; do
        sleep "$interval"
        collect_ollama_metrics 2>/dev/null || true
    done
fi

# Modo teste: exibir métricas
if [ "${1:-}" = "--test" ]; then
    cat "$METRICS_FILE"
fi
