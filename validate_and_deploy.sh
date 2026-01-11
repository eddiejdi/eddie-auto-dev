#!/bin/bash
# Script para validar e fazer deploy

echo "=== Validando arquivo local ==="
python3 -m py_compile /home/eddie/myClaude/specialized_agents/streamlit_app.py
if [ $? -eq 0 ]; then
    echo "✅ Arquivo local OK"
else
    echo "❌ Erro no arquivo local"
    exit 1
fi

echo ""
echo "=== Fazendo git push ==="
cd /home/eddie/myClaude
git add specialized_agents/streamlit_app.py
git commit -m "Fix syntax errors" 2>/dev/null || echo "Nada para commit"
git push origin main

echo ""
echo "=== Atualizando servidor ==="
ssh homelab@192.168.15.2 "cd /home/homelab/myClaude && git pull origin main"

echo ""
echo "=== Validando no servidor ==="
ssh homelab@192.168.15.2 "python3 -m py_compile /home/homelab/myClaude/specialized_agents/streamlit_app.py && echo '✅ Servidor OK' || echo '❌ Erro no servidor'"

echo ""
echo "=== Reiniciando streamlit ==="
ssh homelab@192.168.15.2 "pkill -f 'streamlit.*8502' 2>/dev/null; sleep 2; cd /home/homelab/myClaude && nohup /home/homelab/.local/bin/streamlit run specialized_agents/streamlit_app.py --server.port 8502 --server.address 0.0.0.0 --server.headless true > /tmp/streamlit.log 2>&1 &"

sleep 3
echo ""
echo "=== Verificando porta 8502 ==="
ssh homelab@192.168.15.2 "ss -tlnp | grep 8502 && echo '✅ Streamlit rodando' || echo '❌ Streamlit não iniciou'"

echo ""
echo "=== Logs ==="
ssh homelab@192.168.15.2 "tail -20 /tmp/streamlit.log"
