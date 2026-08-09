#!/bin/bash
# Smart Training Script - Treina apenas quando o sistema está ocioso
# Verifica carga do sistema, memória e conexões antes de treinar

LOG_FILE="/var/log/python-training.log"
LOCK_FILE="/tmp/training.lock"
LAST_TRAIN_FILE="/tmp/last_training_time"
MIN_INTERVAL_HOURS=4

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Verificar se já existe um treinamento em andamento
if [ -f "$LOCK_FILE" ]; then
    log "Treinamento já em andamento, saindo..."
    exit 0
fi

# Verificar intervalo mínimo desde o último treinamento
if [ -f "$LAST_TRAIN_FILE" ]; then
    LAST_TRAIN=$(cat "$LAST_TRAIN_FILE")
    NOW=$(date +%s)
    DIFF_HOURS=$(( (NOW - LAST_TRAIN) / 3600 ))
    
    if [ $DIFF_HOURS -lt $MIN_INTERVAL_HOURS ]; then
        log "Ultimo treinamento foi ha ${DIFF_HOURS}h (minimo: ${MIN_INTERVAL_HOURS}h), pulando..."
        exit 0
    fi
fi

# Verificar carga do sistema (load average nos últimos 5 minutos)
LOAD_5MIN=$(cat /proc/loadavg | awk '{print $2}')
CPU_CORES=$(nproc)
LOAD_THRESHOLD=$(echo "$CPU_CORES * 0.3" | bc)

# Comparar load com threshold (30% da capacidade)
LOAD_HIGH=$(echo "$LOAD_5MIN > $LOAD_THRESHOLD" | bc -l)
if [ "$LOAD_HIGH" -eq 1 ]; then
    log "Sistema ocupado (load: $LOAD_5MIN, threshold: $LOAD_THRESHOLD), pulando..."
    exit 0
fi

# Verificar se Ollama está processando requisições
OLLAMA_CONNECTIONS=$(ss -tn 2>/dev/null | grep -c ":11434" || echo "0")
if [ "$OLLAMA_CONNECTIONS" -gt 2 ]; then
    log "Ollama ocupado ($OLLAMA_CONNECTIONS conexoes ativas), pulando..."
    exit 0
fi

# Verificar memória disponível (mínimo 8GB livres)
FREE_MEM_GB=$(free -g | awk '/^Mem:/ {print $7}')
if [ "$FREE_MEM_GB" -lt 8 ]; then
    log "Memoria insuficiente (${FREE_MEM_GB}GB livres, minimo: 8GB), pulando..."
    exit 0
fi

# Sistema está ocioso - iniciar treinamento
log "=== INICIANDO TREINAMENTO (load: $LOAD_5MIN, mem: ${FREE_MEM_GB}GB livres) ==="
touch "$LOCK_FILE"

# Executar treinamento do RAG
log "Acionando ciclo de aprendizado do RAG..."
RESPONSE=$(curl -s -X POST "http://localhost:8001/api/v1/rag/agent/learn" \
    -H "Content-Type: application/json" \
    -d '{"force": false}' 2>&1)
log "RAG response: $RESPONSE"

# Executar script de treinamento Python se existir
if [ -f "/home/homelab/train_python_docs.sh" ]; then
    log "Executando treinamento Python docs..."
    /bin/bash /home/homelab/train_python_docs.sh >> "$LOG_FILE" 2>&1
fi

# Atualizar timestamp do último treinamento
date +%s > "$LAST_TRAIN_FILE"

# Remover lock
rm -f "$LOCK_FILE"
log "=== TREINAMENTO CONCLUIDO ==="
