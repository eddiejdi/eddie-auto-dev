#!/bin/bash
# Deploy script para DEV_20260109172705
# Gerado automaticamente

set -e

echo "Deployando Obter Cotação do Dólar..."

# Instalar dependências
pip3 install --user -r requirements.txt


# Tornar executável
chmod +x main.py

echo "Deploy concluído!"
