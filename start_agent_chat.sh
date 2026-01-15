#!/bin/bash
# Start Agent Chat Panel

cd /home/homelab/myClaude

# Ativa venv
source venv/bin/activate

# Mata processo anterior se existir
pkill -f "streamlit run.*agent_chat" 2>/dev/null
sleep 2

# Inicia o Agent Chat na porta 8505
echo "🚀 Iniciando Agent Chat na porta 8505..."
nohup streamlit run specialized_agents/agent_chat.py \
    --server.port 8505 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    > /tmp/agent_chat.log 2>&1 &

sleep 3

# Verifica se iniciou
if pgrep -f "streamlit run.*agent_chat" > /dev/null; then
    echo "✅ Agent Chat rodando em http://$(hostname -I | awk '{print $1}'):8505"
    tail -5 /tmp/agent_chat.log
else
    echo "❌ Falha ao iniciar Agent Chat"
    cat /tmp/agent_chat.log
    exit 1
fi
