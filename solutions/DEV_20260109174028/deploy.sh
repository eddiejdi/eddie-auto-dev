#!/bin/bash
# Deploy script para DEV_20260109174028
# Gerado automaticamente

set -e

echo "Deployando API para obter cotação do dólar..."

# Instalar dependências
pip3 install --user -r requirements.txt


# Tornar executável
chmod +x main.py

echo "Deploy concluído!"
