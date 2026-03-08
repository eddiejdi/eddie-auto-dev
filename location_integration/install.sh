#!/bin/bash
# Script de instalação do servidor de localização

echo "🌍 Instalando Shared Location Server..."
echo ""

# Diretório do projeto
PROJECT_DIR="$HOME/myClaude/location_integration"
cd "$PROJECT_DIR"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado!"
    exit 1
fi

# Criar venv se não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar venv e instalar dependências
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn httpx

# Criar diretório de dados
mkdir -p data

# Criar service do systemd
SERVICE_FILE="/etc/systemd/system/shared-location.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Shared Location Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python location_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Habilitar e iniciar serviço
sudo systemctl daemon-reload
sudo systemctl enable shared-location
sudo systemctl start shared-location

echo ""
echo "✅ Instalação concluída!"
echo ""
echo "📱 Configure o OwnTracks no seu celular:"
echo "   1. Baixe OwnTracks na Play Store"
echo "   2. Vá em Configurações → Conexão"
echo "   3. Modo: HTTP"
echo "   4. URL: http://$(hostname -I | awk '{print $1}'):8585/owntracks"
echo "   5. Identificador: shared (ou seu nome)"
echo ""
echo "🔧 Comandos úteis:"
echo "   sudo systemctl status shared-location  # Ver status"
echo "   sudo journalctl -u shared-location -f  # Ver logs"
echo "   curl http://localhost:8585/status     # Testar API"
echo ""
