#!/bin/bash
# Deploy script para DEV_20260109163517
# Gerado automaticamente

set -e

echo "Deployando Teste de Deploy..."

# Instalar dependências
pip3 install --user -r requirements.txt


# Tornar executável
chmod +x main.py

echo "Deploy concluído!"
