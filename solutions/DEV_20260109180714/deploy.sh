#!/bin/bash
# Deploy script para DEV_20260109180714
# Gerado automaticamente

set -e

echo "Deployando Previsão de Tempo para Jundiaí..."

# Instalar dependências
pip3 install --user -r requirements.txt


# Tornar executável
chmod +x main.py

echo "Deploy concluído!"
