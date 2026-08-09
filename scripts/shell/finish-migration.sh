#!/bin/bash
LOG=/tmp/migration-dual-model.log
exec >> $LOG 2>&1
step() { echo "[$(date +%H:%M:%S)] $*"; }

step "Aguardando pull-with-retry qwen3:8b..."
wait $(pgrep -f "pull-with-retry.sh qwen3:8b") 2>/dev/null || true
while ! OLLAMA_HOST=http://127.0.0.1:11434 ollama list 2>/dev/null | grep -q "qwen3:8b"; do
    grep -q "EXIT=0" /tmp/pull-qwen3-8b.log 2>/dev/null && break
    grep -q "EXIT=1" /tmp/pull-qwen3-8b.log 2>/dev/null && { step "ERRO: pull qwen3:8b falhou"; exit 1; }
    sleep 30
done
step "qwen3:8b disponivel"

step "Aguardando pull-with-retry qwen3:1.7b..."
while ! OLLAMA_HOST=http://127.0.0.1:11434 ollama list 2>/dev/null | grep -q "qwen3:1.7b"; do
    grep -q "EXIT=0" /tmp/pull-qwen3-1.7b.log 2>/dev/null && break
    grep -q "EXIT=1" /tmp/pull-qwen3-1.7b.log 2>/dev/null && { step "ERRO: pull qwen3:1.7b falhou"; exit 1; }
    sleep 20
done
step "qwen3:1.7b disponivel"

step "Recriando trading-analyst com qwen3:8b..."
OLLAMA_HOST=http://127.0.0.1:11434 ollama create trading-analyst -f /tmp/Modelfile-trading-analyst-8b
step "trading-analyst recriado"

step "Reiniciando ollama.service..."
sudo systemctl restart ollama.service
sleep 35

step "Modelos em VRAM:"
curl -s http://127.0.0.1:11434/api/ps | python3 -c "
import json,sys
d=json.load(sys.stdin)
for m in d.get(models,[]):
    print( -, m[name], round(m.get(size_vram,0)/1e9,2), GB VRAM)
"
step "Migracao concluida."
