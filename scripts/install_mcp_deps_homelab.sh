#!/bin/bash
# Instalação de dependências MCP no Homelab
# Resolve dependências faltantes detectadas pelos testes

set -e

HOMELAB_HOST="homelab@192.168.15.2"
HOMELAB_VENV="/home/homelab/shared-auto-dev/.venv"

echo "=============================================================================="
echo "🔧 INSTALAÇÃO DE DEPENDÊNCIAS MCP NO HOMELAB"
echo "=============================================================================="
echo ""

# Verificar conectividade SSH
echo "📡 Verificando conectividade SSH com homelab..."
if ssh "$HOMELAB_HOST" "echo 'SSH_OK'" | grep -q "SSH_OK"; then
    echo "✅ Conexão SSH estabelecida"
else
    echo "❌ Falha na conexão SSH com $HOMELAB_HOST"
    exit 1
fi
echo ""

# Verificar venv
echo "🐍 Verificando ambiente virtual Python..."
if ssh "$HOMELAB_HOST" "test -d $HOMELAB_VENV && echo 'VENV_OK'" | grep -q "VENV_OK"; then
    echo "✅ Virtual environment encontrado: $HOMELAB_VENV"
else
    echo "⚠️  Virtual environment não encontrado"
    echo "   Criando novo venv..."
    ssh "$HOMELAB_HOST" "cd /home/homelab/shared-auto-dev && python3 -m venv .venv"
    echo "✅ Virtual environment criado"
fi
echo ""

# Instalar dependências MCP
echo "📦 Instalando dependências MCP..."
echo ""

echo "1️⃣  Instalando pacote 'mcp' (Model Context Protocol SDK)..."
ssh "$HOMELAB_HOST" "$HOMELAB_VENV/bin/pip install -q mcp && echo '✅ mcp instalado' || echo '❌ Falha: mcp'"

echo "2️⃣  Instalando pacote 'httpx' (HTTP client)..."
ssh "$HOMELAB_HOST" "$HOMELAB_VENV/bin/pip install -q httpx && echo '✅ httpx instalado' || echo '⚠️  httpx já instalado'"

echo "3️⃣  Instalando pacote 'paramiko' (SSH client)..."
ssh "$HOMELAB_HOST" "$HOMELAB_VENV/bin/pip install -q paramiko && echo '✅ paramiko instalado' || echo '❌ Falha: paramiko'"

echo "4️⃣  Instalando pacote 'chromadb' (Vector DB)..."
ssh "$HOMELAB_HOST" "$HOMELAB_VENV/bin/pip install -q chromadb && echo '✅ chromadb instalado' || echo '⚠️  chromadb já instalado'"

echo ""

# Verificar instalação
echo "=============================================================================="
echo "🔍 VERIFICANDO INSTALAÇÃO"
echo "=============================================================================="
echo ""

echo "Pacotes instalados no homelab:"
ssh "$HOMELAB_HOST" "$HOMELAB_VENV/bin/pip list | grep -E '(mcp|httpx|paramiko|chromadb)'"

echo ""
echo "=============================================================================="
echo "✅ INSTALAÇÃO CONCLUÍDA!"
echo "=============================================================================="
echo ""
echo "Próximo passo: Executar testes de validação"
echo "  python3 scripts/test_pycharm_mcp.py"
echo ""

