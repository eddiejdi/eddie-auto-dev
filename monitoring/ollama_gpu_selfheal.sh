#!/bin/bash
# ===================================================================
# Ollama Dual-GPU Selfheal & Metrics Exporter
# Monitora GPU0 (RTX 2060, :11434) e GPU1 (GTX 1050, :11435)
# Detecta runner frozen → restart automático → alerta Telegram
# Exporta métricas para Prometheus via node-exporter textfile collector
# ===================================================================
set -euo pipefail

# --- Configuração -----------------------------------------------
GPU0_HOST="${OLLAMA_HOST_GPU0:-http://192.168.15.2:11434}"
GPU1_HOST="${OLLAMA_HOST_GPU1:-http://192.168.15.2:11435}"
GPU0_SERVICE="${OLLAMA_SERVICE_GPU0:-ollama}"
GPU1_SERVICE="${OLLAMA_SERVICE_GPU1:-ollama-gpu1}"

TEXTFILE_DIR="/var/lib/prometheus/node-exporter"
PROM_FILE="${TEXTFILE_DIR}/ollama_gpu.prom"
TMP_FILE="/tmp/ollama_gpu_metrics.prom.$$"

CHECK_INTERVAL="${CHECK_INTERVAL:-15}"
FROZEN_THRESHOLD="${FROZEN_THRESHOLD:-120}"
GENERATE_TIMEOUT="${GENERATE_TIMEOUT:-30}"
MAX_RESTARTS_HOUR="${MAX_RESTARTS_HOUR:-3}"

STATE_DIR="/var/lib/ollama-selfheal"
LOG_TAG="ollama-gpu-selfheal"

# --- Inicialização -----------------------------------------------
mkdir -p "$STATE_DIR" 2>/dev/null || true
for gpu in gpu0 gpu1; do
    [ -f "$STATE_DIR/${gpu}_last_ok" ]    || date +%s > "$STATE_DIR/${gpu}_last_ok"
    [ -f "$STATE_DIR/${gpu}_restarts" ]   || echo "0" > "$STATE_DIR/${gpu}_restarts"
    [ -f "$STATE_DIR/${gpu}_restart_ts" ] || echo "0" > "$STATE_DIR/${gpu}_restart_ts"
done

log() { logger -t "$LOG_TAG" -p "daemon.${1}" "${2}"; }

# --- Funções de probe --------------------------------------------
# Probe leve: /api/tags responde?
probe_alive() {
    local host="$1"
    curl -sf --max-time 3 "${host}/api/tags" >/dev/null 2>&1
}

# Probe pesado: /api/generate produz tokens?
probe_generate() {
    local host="$1" model="$2"
    local resp
    resp=$(curl -sf --max-time "$GENERATE_TIMEOUT" \
        -d "{\"model\":\"${model}\",\"prompt\":\"ping\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
        "${host}/api/generate" 2>/dev/null) || return 1
    echo "$resp" | grep -q '"done":true'
}

# Descobrir modelo ativo num host
active_model() {
    local host="$1"
    curl -sf --max-time 3 "${host}/api/ps" 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['models'][0]['name'] if d.get('models') else '')" 2>/dev/null || echo ""
}

# --- Selfheal ----------------------------------------------------
do_restart() {
    local gpu="$1" service="$2"
    local count_file="$STATE_DIR/${gpu}_restarts"
    local ts_file="$STATE_DIR/${gpu}_restart_ts"
    local count last_ts now

    count=$(cat "$count_file" 2>/dev/null || echo 0)
    last_ts=$(cat "$ts_file" 2>/dev/null || echo 0)
    now=$(date +%s)

    # Resetar contador se passou mais de 1h desde o último restart
    if (( now - last_ts > 3600 )); then
        count=0
    fi

    if (( count >= MAX_RESTARTS_HOUR )); then
        log "crit" "${gpu}: rate-limit atingido (${count}/${MAX_RESTARTS_HOUR} restarts/h) — escalar manualmente"
        return 1
    fi

    log "warning" "${gpu}: executando restart de ${service}..."
    if systemctl restart "$service" 2>/dev/null; then
        count=$((count + 1))
        echo "$count" > "$count_file"
        echo "$now"   > "$ts_file"
        log "info" "${gpu}: restart OK (${count}/${MAX_RESTARTS_HOUR} na última hora)"
        # Dar tempo para o modelo carregar
        sleep 15
        return 0
    else
        log "crit" "${gpu}: falha no restart de ${service}"
        return 1
    fi
}

# --- Coleta de métricas ------------------------------------------
collect_gpu_nvidia() {
    local idx="$1" # 0 ou 1
    local util mem_used mem_total temp power
    util=$(nvidia-smi -i "$idx" --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || util=""
    mem_used=$(nvidia-smi -i "$idx" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || mem_used=""
    mem_total=$(nvidia-smi -i "$idx" --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || mem_total=""
    temp=$(nvidia-smi -i "$idx" --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || temp=""
    power=$(nvidia-smi -i "$idx" --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || power=""
    # Sanitizar [N/A] (ex: GTX 1050 não reporta power.draw)
    [[ "$util" == *N/A* ]]      && util=""
    [[ "$mem_used" == *N/A* ]]  && mem_used=""
    [[ "$mem_total" == *N/A* ]] && mem_total=""
    [[ "$temp" == *N/A* ]]      && temp=""
    [[ "$power" == *N/A* ]]     && power=""
    echo "${util:-0} ${mem_used:-0} ${mem_total:-0} ${temp:-0} ${power:-0}"
}

write_metrics() {
    local gpu0_up="$1" gpu1_up="$2"
    local gpu0_frozen="$3" gpu1_frozen="$4"
    local gpu0_restarts="$5" gpu1_restarts="$6"
    local gpu0_model="$7" gpu1_model="$8"
    local gpu0_responsive="$9" gpu1_responsive="${10}"

    > "$TMP_FILE"

    # Per-GPU metrics
    cat >> "$TMP_FILE" <<'HEADER'
# HELP ollama_gpu_up Ollama instance reachable (api/tags responds)
# TYPE ollama_gpu_up gauge
# HELP ollama_gpu_responsive Ollama generate actually produces tokens
# TYPE ollama_gpu_responsive gauge
# HELP ollama_gpu_frozen_seconds Seconds since last successful generate
# TYPE ollama_gpu_frozen_seconds gauge
# HELP ollama_gpu_selfheal_restarts_total Automatic restarts triggered
# TYPE ollama_gpu_selfheal_restarts_total counter
# HELP ollama_gpu_util_percent GPU utilization percent
# TYPE ollama_gpu_util_percent gauge
# HELP ollama_gpu_memory_used_mib GPU memory used in MiB
# TYPE ollama_gpu_memory_used_mib gauge
# HELP ollama_gpu_memory_total_mib GPU memory total in MiB
# TYPE ollama_gpu_memory_total_mib gauge
# HELP ollama_gpu_temperature_celsius GPU temperature
# TYPE ollama_gpu_temperature_celsius gauge
# HELP ollama_gpu_power_watts GPU power draw
# TYPE ollama_gpu_power_watts gauge
HEADER

    local idx=0
    for gpu in gpu0 gpu1; do
        local up frozen restarts model responsive
        if [ "$gpu" = "gpu0" ]; then
            up=$gpu0_up; frozen=$gpu0_frozen; restarts=$gpu0_restarts
            model=$gpu0_model; responsive=$gpu0_responsive
        else
            up=$gpu1_up; frozen=$gpu1_frozen; restarts=$gpu1_restarts
            model=$gpu1_model; responsive=$gpu1_responsive
        fi
        local label="{gpu=\"${gpu}\",model=\"${model}\"}"
        echo "ollama_gpu_up${label} ${up}" >> "$TMP_FILE"
        echo "ollama_gpu_responsive${label} ${responsive}" >> "$TMP_FILE"
        echo "ollama_gpu_frozen_seconds${label} ${frozen}" >> "$TMP_FILE"
        echo "ollama_gpu_selfheal_restarts_total${label} ${restarts}" >> "$TMP_FILE"

        # nvidia-smi
        read -r util mem_used mem_total temp power <<< "$(collect_gpu_nvidia $idx)"
        local hw="{gpu=\"${gpu}\"}"
        echo "ollama_gpu_util_percent${hw} ${util}" >> "$TMP_FILE"
        echo "ollama_gpu_memory_used_mib${hw} ${mem_used}" >> "$TMP_FILE"
        echo "ollama_gpu_memory_total_mib${hw} ${mem_total}" >> "$TMP_FILE"
        echo "ollama_gpu_temperature_celsius${hw} ${temp}" >> "$TMP_FILE"
        echo "ollama_gpu_power_watts${hw} ${power}" >> "$TMP_FILE"

        idx=$((idx + 1))
    done

    # Atomic write
    chmod 644 "$TMP_FILE" 2>/dev/null || true
    mv "$TMP_FILE" "$PROM_FILE"
}

# --- Loop principal -----------------------------------------------
check_gpu() {
    local gpu="$1" host="$2" service="$3"
    local now up=0 responsive=0 frozen_secs=0
    now=$(date +%s)

    # 1) Probe leve
    if probe_alive "$host"; then
        up=1
        # 2) Descobrir modelo
        local model
        model=$(active_model "$host")
        if [ -n "$model" ]; then
            # 3) Probe pesado
            if probe_generate "$host" "$model"; then
                responsive=1
                echo "$now" > "$STATE_DIR/${gpu}_last_ok"
            else
                # Heurística: se GPU util >50% e modelo carregado, está ocupada (não frozen)
                local gpu_idx
                [[ "$gpu" == "gpu0" ]] && gpu_idx=0 || gpu_idx=1
                local cur_util
                cur_util=$(nvidia-smi -i "$gpu_idx" --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | tr -d ' ') || cur_util="0"
                [[ "$cur_util" == *N/A* ]] && cur_util="0"
                if (( cur_util > 50 )); then
                    log "info" "${gpu}: generate timeout mas GPU util=${cur_util}% — considerando ocupada, não frozen"
                    responsive=1
                    echo "$now" > "$STATE_DIR/${gpu}_last_ok"
                fi
            fi
        else
            # Sem modelo carregado — responsivo mas ocioso
            responsive=1
            echo "$now" > "$STATE_DIR/${gpu}_last_ok"
        fi
    fi

    local last_ok
    last_ok=$(cat "$STATE_DIR/${gpu}_last_ok" 2>/dev/null || echo "$now")
    frozen_secs=$((now - last_ok))

    # 4) Selfheal se frozen > threshold
    if (( frozen_secs > FROZEN_THRESHOLD )) && (( up == 1 )); then
        log "crit" "${gpu}: frozen há ${frozen_secs}s (threshold=${FROZEN_THRESHOLD}s) — iniciando selfheal"
        if do_restart "$gpu" "$service"; then
            # Re-probe após restart
            if probe_alive "$host"; then
                up=1
                local m
                m=$(active_model "$host")
                if [ -n "$m" ] && probe_generate "$host" "$m"; then
                    responsive=1
                    echo "$(date +%s)" > "$STATE_DIR/${gpu}_last_ok"
                    frozen_secs=0
                    log "info" "${gpu}: selfheal bem-sucedido — modelo ${m} respondendo"
                fi
            fi
        fi
    elif (( up == 0 )); then
        # Service down (não responde sequer tags) — restart
        if (( frozen_secs > FROZEN_THRESHOLD )); then
            log "crit" "${gpu}: service down há ${frozen_secs}s — tentando restart"
            do_restart "$gpu" "$service" || true
        fi
    fi

    local restarts
    restarts=$(cat "$STATE_DIR/${gpu}_restarts" 2>/dev/null || echo 0)
    local model_name
    model_name=$(active_model "$host" 2>/dev/null || echo "none")

    echo "$up $responsive $frozen_secs $restarts $model_name"
}

main_loop() {
    log "info" "Iniciando monitoramento dual-GPU (GPU0=${GPU0_HOST}, GPU1=${GPU1_HOST}, interval=${CHECK_INTERVAL}s, threshold=${FROZEN_THRESHOLD}s)"

    while true; do
        local gpu0_result gpu1_result
        gpu0_result=$(check_gpu "gpu0" "$GPU0_HOST" "$GPU0_SERVICE")
        gpu1_result=$(check_gpu "gpu1" "$GPU1_HOST" "$GPU1_SERVICE")

        read -r g0_up g0_resp g0_frozen g0_restarts g0_model <<< "$gpu0_result"
        read -r g1_up g1_resp g1_frozen g1_restarts g1_model <<< "$gpu1_result"

        write_metrics "$g0_up" "$g1_up" "$g0_frozen" "$g1_frozen" \
                      "$g0_restarts" "$g1_restarts" "${g0_model:-none}" "${g1_model:-none}" \
                      "$g0_resp" "$g1_resp"

        sleep "$CHECK_INTERVAL"
    done
}

# --- Entrypoint ---------------------------------------------------
case "${1:-}" in
    --test)
        echo "=== GPU0 ($GPU0_HOST) ==="
        check_gpu "gpu0" "$GPU0_HOST" "$GPU0_SERVICE"
        echo "=== GPU1 ($GPU1_HOST) ==="
        check_gpu "gpu1" "$GPU1_HOST" "$GPU1_SERVICE"
        cat "$PROM_FILE" 2>/dev/null || echo "(sem métricas ainda)"
        ;;
    --once)
        gpu0_result=$(check_gpu "gpu0" "$GPU0_HOST" "$GPU0_SERVICE")
        gpu1_result=$(check_gpu "gpu1" "$GPU1_HOST" "$GPU1_SERVICE")
        read -r g0_up g0_resp g0_frozen g0_restarts g0_model <<< "$gpu0_result"
        read -r g1_up g1_resp g1_frozen g1_restarts g1_model <<< "$gpu1_result"
        write_metrics "$g0_up" "$g1_up" "$g0_frozen" "$g1_frozen" \
                      "$g0_restarts" "$g1_restarts" "${g0_model:-none}" "${g1_model:-none}" \
                      "$g0_resp" "$g1_resp"
        echo "Métricas escritas em $PROM_FILE"
        cat "$PROM_FILE"
        ;;
    *)
        main_loop
        ;;
esac
