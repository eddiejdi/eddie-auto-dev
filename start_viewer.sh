#!/bin/bash
# Script para iniciar o Streamlit de forma persistente

cd /home/eddie/myClaude
source .venv/bin/activate

# Matar processos anteriores
pkill -9 -f "streamlit run" 2>/dev/null || true
sleep 1

# Iniciar Streamlit em background
nohup python -m streamlit run specialized_agents/simple_conversation_viewer.py \
    --server.port=8501 \
    --server.headless=true \
    --server.address=0.0.0.0 \
    > /tmp/streamlit_viewer.log 2>&1 &

echo "PID: $!"
sleep 3

# Verificar se iniciou
if pgrep -f "streamlit run" > /dev/null; then
    echo "✅ Streamlit iniciado com sucesso!"
    curl -s https://heights-treasure-auto-phones.trycloudflare.com/_stcore/health && echo " - Health OK"
else
    echo "❌ Falha ao iniciar Streamlit"
    cat /tmp/streamlit_viewer.log
    exit 1
fi
