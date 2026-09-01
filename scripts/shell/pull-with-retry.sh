#!/bin/bash
# Pull com retry automatico — contorna DNS timeout:1 attempts:1
MODEL=$1
LOG=$2
MAX_ATTEMPTS=20

echo "[$(date +%H:%M:%S)] Iniciando pull $MODEL (max $MAX_ATTEMPTS tentativas)"

for i in $(seq 1 $MAX_ATTEMPTS); do
    echo "[$(date +%H:%M:%S)] Tentativa $i/$MAX_ATTEMPTS..."
    if OLLAMA_HOST=http://127.0.0.1:11434 /usr/local/bin/ollama pull "$MODEL" >> "$LOG" 2>&1; then
        echo "EXIT=0" >> "$LOG"
        echo "[$(date +%H:%M:%S)] Pull $MODEL concluido na tentativa $i"
        exit 0
    fi
    echo "[$(date +%H:%M:%S)] Tentativa $i falhou, aguardando 15s antes de retry..."
    sleep 15
done

echo "EXIT=1" >> "$LOG"
echo "[$(date +%H:%M:%S)] ERRO: $MODEL falhou apos $MAX_ATTEMPTS tentativas"
exit 1
