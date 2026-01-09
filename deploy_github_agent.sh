#!/bin/bash

# Deploy GitHub Agent to Homelab Server
# Server: 192.168.15.2

SERVER="homelab@192.168.15.2"
REMOTE_DIR="/home/homelab/github-agent"
PASSWORD="homelab"  # Substitua pela senha real

echo "=== GitHub Agent Deploy Script ==="

# Função para executar comandos SSH com sshpass
ssh_cmd() {
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $SERVER "$1"
}

scp_cmd() {
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$1" "$SERVER:$2"
}

echo "1. Criando diretório no servidor..."
ssh_cmd "mkdir -p $REMOTE_DIR/templates"

echo "2. Copiando arquivos..."
scp_cmd "github_agent_streamlit.py" "$REMOTE_DIR/"

echo "3. Criando ambiente virtual e instalando dependências..."
ssh_cmd "cd $REMOTE_DIR && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install streamlit requests"

echo "4. Criando arquivo de serviço systemd..."
ssh_cmd "cat > /tmp/github-agent.service << 'EOF'
[Unit]
Description=GitHub Agent Streamlit Service
After=network.target ollama.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/github-agent
Environment=OLLAMA_HOST=http://localhost:11434
ExecStart=/home/homelab/github-agent/venv/bin/streamlit run github_agent_streamlit.py --server.port 8502 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

echo "5. Instalando serviço systemd..."
ssh_cmd "sudo mv /tmp/github-agent.service /etc/systemd/system/"
ssh_cmd "sudo systemctl daemon-reload"
ssh_cmd "sudo systemctl enable github-agent"
ssh_cmd "sudo systemctl start github-agent"

echo "6. Verificando status..."
ssh_cmd "sudo systemctl status github-agent --no-pager"

echo ""
echo "=== Deploy completo! ==="
echo "Acesse: http://192.168.15.2:8502"
