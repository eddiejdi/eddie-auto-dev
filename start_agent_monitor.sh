#!/bin/bash
# Iniciar Agent Monitor

source /home/homelab/myClaude/venv/bin/activate

# Matar processo anterior se existir
pkill -f "streamlit.*agent_monitor" 2>/dev/null
sleep 1

# Iniciar monitor na porta 8504
nohup streamlit run /home/homelab/myClaude/specialized_agents/agent_monitor.py \
    --server.port 8504 \
    --server.address 0.0.0.0 \
    --server.headless true \
    > /tmp/agent_monitor.log 2>&1 &

echo "Aguardando inicialização..."
sleep 3

# Verificar se iniciou
if pgrep -f "streamlit.*agent_monitor" > /dev/null; then
    echo "✅ Agent Monitor iniciado na porta 8504"
    echo "Acesse: http://192.168.15.2:8504"
else
    echo "❌ Erro ao iniciar"
    cat /tmp/agent_monitor.log
fi
