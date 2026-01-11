#!/bin/bash

# =============================================================================
# Setup GitHub MCP Server para todas as extensões de IA
# =============================================================================

echo "🚀 GitHub MCP Server - Setup Automático"
echo "========================================"

MCP_DIR="/home/homelab/myClaude/github-mcp-server"
CONTINUE_CONFIG="$HOME/.continue/config.json"
CLINE_CONFIG="$HOME/.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
ROO_CONFIG="$HOME/.vscode-server/data/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json"

# Verificar token GitHub
if [ -z "$GITHUB_TOKEN" ]; then
    echo ""
    echo "⚠️  GITHUB_TOKEN não definido!"
    echo ""
    echo "1. Crie um token em: https://github.com/settings/tokens/new"
    echo "2. Selecione os scopes: repo, read:user, read:org, gist, notifications, workflow"
    echo "3. Execute:"
    echo "   export GITHUB_TOKEN='ghp_seu_token_aqui'"
    echo "   echo 'export GITHUB_TOKEN=\"ghp_seu_token_aqui\"' >> ~/.bashrc"
    echo ""
    read -p "Cole seu GitHub Token: " GITHUB_TOKEN
    
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "export GITHUB_TOKEN=\"$GITHUB_TOKEN\"" >> ~/.bashrc
        export GITHUB_TOKEN
        echo "✅ Token salvo em ~/.bashrc"
    fi
fi

# Instalar dependências
echo ""
echo "📦 Instalando dependências..."
cd "$MCP_DIR"
if [ -d "venv" ]; then
    source venv/bin/activate
else
    python3 -m venv venv
    source venv/bin/activate
fi
pip install -q mcp httpx
echo "✅ Dependências instaladas"

# Configurar Continue
echo ""
echo "🔧 Configurando Continue..."
mkdir -p "$(dirname $CONTINUE_CONFIG)"
if [ -f "$CONTINUE_CONFIG" ]; then
    echo "   ⚠️  Arquivo existente encontrado. Backup criado."
    cp "$CONTINUE_CONFIG" "${CONTINUE_CONFIG}.backup"
fi
cp "$MCP_DIR/config/continue-config.json" "$CONTINUE_CONFIG"
# Substituir token
sed -i "s/\${GITHUB_TOKEN}/$GITHUB_TOKEN/g" "$CONTINUE_CONFIG"
echo "✅ Continue configurado"

# Configurar Cline (se instalado)
if [ -d "$(dirname $CLINE_CONFIG)" ]; then
    echo ""
    echo "🔧 Configurando Cline..."
    cp "$MCP_DIR/config/cline-mcp-settings.json" "$CLINE_CONFIG"
    sed -i "s/\${GITHUB_TOKEN}/$GITHUB_TOKEN/g" "$CLINE_CONFIG"
    echo "✅ Cline configurado"
fi

# Configurar Roo Code (se instalado)
if [ -d "$(dirname $ROO_CONFIG)" ]; then
    echo ""
    echo "🔧 Configurando Roo Code..."
    mkdir -p "$(dirname $ROO_CONFIG)"
    cp "$MCP_DIR/config/roo-code-mcp-settings.json" "$ROO_CONFIG"
    sed -i "s/\${GITHUB_TOKEN}/$GITHUB_TOKEN/g" "$ROO_CONFIG"
    echo "✅ Roo Code configurado"
fi

echo ""
echo "========================================"
echo "✅ Setup completo!"
echo ""
echo "📍 MCP Server: $MCP_DIR/src/github_mcp_server.py"
echo ""
echo "🔑 Ferramentas disponíveis:"
echo "   - github_set_token"
echo "   - github_list_repos"
echo "   - github_create_issue"
echo "   - github_list_prs"
echo "   - github_search_code"
echo "   - E mais 30+ ferramentas!"
echo ""
echo "💡 Para testar, reinicie o VS Code e pergunte:"
echo '   "Liste meus repositórios do GitHub"'
echo ""
