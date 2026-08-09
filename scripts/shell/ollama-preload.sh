#!/bin/bash
# Preload qwen2.5-coder:7b-ctx4k after Ollama startup
# Ensures model loads with 4096 context and 4 GPU layers before any client interferes

MODEL="qwen2.5-coder:7b-ctx4k"
MAX_WAIT=60
OLLAMA_URL="http://localhost:11434"

echo "[$(date)] Waiting for Ollama to be ready..."
for i in $(seq 1 $MAX_WAIT); do
    if curl -s --max-time 2 "$OLLAMA_URL/" > /dev/null 2>&1; then
        echo "[$(date)] Ollama ready after ${i}s"
        break
    fi
    sleep 1
done

echo "[$(date)] Preloading $MODEL with num_ctx=4096..."
curl -s --max-time 120 "$OLLAMA_URL/api/generate" \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"warmup\",\"stream\":false,\"options\":{\"num_ctx\":4096}}" \
    > /dev/null 2>&1

echo "[$(date)] Model preloaded. Checking status..."
curl -s --max-time 5 "$OLLAMA_URL/api/ps" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get(\"models\"):
    m=d[\"models\"][0]
    print(f\"  Model: {m[\"name\"]}\")
    print(f\"  Context: {m.get(\"context_length\",\"?\")}\")
    print(f\"  VRAM: {m[\"size_vram\"]/(1024**2):.0f} MiB\")
else:
    print(\"  No models loaded!\")
" 2>&1
echo "[$(date)] Preload complete."
