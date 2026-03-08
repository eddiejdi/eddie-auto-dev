#!/bin/bash
# Monitor GPU usage with Ollama models

HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
MODEL="${MODEL:-qwen2.5-coder:7b}"
INTERVAL=2

echo "═══════════════════════════════════════════════════════════"
echo "  🚀 GPU + OLLAMA MONITOR (GTX 1050)"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "🎯 Target: $HOMELAB_HOST"
echo "📦 Model: $MODEL"
echo "📊 Update interval: ${INTERVAL}s"
echo ""
echo "Press Ctrl+C to exit"
echo ""

test_inference() {
    local prompt="Explain quantum computing in one sentence"
    
    ssh homelab@$HOMELAB_HOST "
    timeout 10 curl -s http://localhost:11434/api/generate \
      -d '{\"model\":\"'$MODEL'\",\"prompt\":\"'$prompt'\",\"stream\":false}' \
      2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'{len(d.get(\\\"response\\\",\\\"\\\"))} tokens')\" || echo 'Model execution timeout'
    " 2>/dev/null
}

while true; do
    clear
    echo "═══════════════════════════════════════════════════════════"
    echo "  $(date '+%Y-%m-%d %H:%M:%S') - GPU MONITOR"
    echo "═══════════════════════════════════════════════════════════"
    
    ssh homelab@$HOMELAB_HOST "
    echo '[GPU Status]'
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw,power.limit \
      --format=csv,noheader,nounits | awk -F',' '{
      gsub(/^ +| +\$/, \"\", \$1)
      printf \"GPU: %s\n  Memory: %s/%s MB\n  GPU Util: %s%%\n  Temp: %s°C\n  Power: %s/%s W\n\",
      \$1, \$2, \$3, \$4, \$5, \$6, \$7
    }'
    
    echo ''
    echo '[Ollama Status]'
    systemctl is-active ollama &>/dev/null && echo '✓ Ollama: RUNNING' || echo '✗ Ollama: STOPPED'
    
    echo ''
    echo '[Test Inference (10s timeout)]'
    timeout 12 curl -s http://localhost:11434/api/generate \
      -d '{\"model\":\"'$MODEL'\",\"prompt\":\"What is AI?\",\"stream\":false}' 2>/dev/null | \
      python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'Response: {d.get(\\\"response\\\",\\\"ERROR\\\")[:100]}...')\" || echo '⏳ Inference timeout or error'
    
    echo ''
    echo '[GPU Processes]'
    nvidia-smi -q -i 0 | grep -A10 'Processes'  | tail -3
    
    echo ''
    echo 'Press Ctrl+C to exit. Updates every '${INTERVAL}'s...'
    sleep $INTERVAL
done
