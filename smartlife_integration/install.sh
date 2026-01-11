#!/bin/bash
# Instalação do SmartLife Integration Service

set -e

echo "=========================================="
echo "  SmartLife Integration - Instalação"
echo "=========================================="

# Diretório do projeto
PROJECT_DIR="/home/homelab/myClaude/smartlife_integration"
cd "$PROJECT_DIR"

# 1. Criar ambiente virtual
echo ""
echo "[1/6] Criando ambiente virtual..."
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependências
echo ""
echo "[2/6] Instalando dependências..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Criar arquivo de configuração
echo ""
echo "[3/6] Configurando..."
if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo "⚠️  Edite config/config.yaml com suas credenciais!"
fi

# 4. Criar diretórios necessários
echo ""
echo "[4/6] Criando diretórios..."
mkdir -p logs
mkdir -p config

# 5. Executar TinyTuya wizard (se credenciais existirem)
echo ""
echo "[5/6] TinyTuya Wizard..."
echo "Para obter os dispositivos, execute:"
echo "  source venv/bin/activate"
echo "  python -m tinytuya wizard"
echo ""

# 6. Instalar serviço systemd
echo ""
echo "[6/6] Instalando serviço systemd..."
sudo cp systemd/eddie-smartlife.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "Serviço instalado!"

echo ""
echo "=========================================="
echo "  Instalação Concluída!"
echo "=========================================="
echo ""
echo "Próximos passos:"
echo ""
echo "1. Configure sua conta Tuya IoT:"
echo "   - Acesse: https://iot.tuya.com"
echo "   - Crie um Cloud Project"
echo "   - Vincule o app SmartLife"
echo "   - Copie API Key e Secret"
echo ""
echo "2. Edite a configuração:"
echo "   nano config/config.yaml"
echo ""
echo "3. Execute o TinyTuya wizard:"
echo "   source venv/bin/activate"
echo "   python -m tinytuya wizard"
echo ""
echo "4. Inicie o serviço:"
echo "   sudo systemctl start eddie-smartlife"
echo "   sudo systemctl enable eddie-smartlife"
echo ""
echo "5. Verifique os logs:"
echo "   journalctl -u eddie-smartlife -f"
echo ""
