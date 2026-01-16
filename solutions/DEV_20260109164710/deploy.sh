#!/bin/bash
# Deploy script para DEV_20260109164710
# Gerado automaticamente

set -e

echo "Deployando Previsão do Tempo para Amanhã..."

# Instalar dependências
pip3 install --user -r requirements.txt


# Tornar executável
chmod +x main.py

echo "Deploy concluído!"
