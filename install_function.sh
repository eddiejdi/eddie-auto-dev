#!/bin/bash
# ==============================================
# INSTALAÇÃO DA FUNÇÃO NO OPEN WEBUI
# ==============================================
# 
# Execute este script passando email e senha:
#   ./install_function.sh seu@email.com suasenha
#
# Ou configure as variáveis de ambiente:
#   export WEBUI_EMAIL="seu@email.com"
#   export WEBUI_PASSWORD="suasenha"
#   ./install_function.sh

cd ~/myClaude
source .venv/bin/activate

EMAIL="${1:-$WEBUI_EMAIL}"
PASSWORD="${2:-$WEBUI_PASSWORD}"

if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
    echo "❌ Uso: $0 <email> <senha>"
    echo "   Ou defina WEBUI_EMAIL e WEBUI_PASSWORD"
    exit 1
fi

echo "🔧 Instalando função no Open WebUI..."
python test_webui_install.py "$EMAIL" "$PASSWORD"
