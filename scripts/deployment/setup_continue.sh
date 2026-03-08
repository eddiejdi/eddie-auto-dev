#!/bin/bash
# Setup automático do Continue.dev para VS Code e PyCharm

set -e

echo "🚀 Shared Auto-Dev — Continue.dev Setup"
echo "========================================"
echo ""

# ============================================================
# 1. VS Code Configuration
# ============================================================

echo "📝 Configurando Continue.dev para VS Code..."

CONTINUE_CONFIG="$HOME/.continue/config.yaml"

if [ ! -f "$CONTINUE_CONFIG" ]; then
    echo "❌ Não encontrado: $CONTINUE_CONFIG"
    echo "   Continue.dev ainda não foi instalado no VS Code."
    echo "   Instale via: Extensions → Continue (marketplace)"
    exit 1
fi

# Verificar se já tem tools configuradas
if grep -q "shared-tools" "$CONTINUE_CONFIG"; then
    echo "✅ VS Code já está configurado com shared-tools"
else
    echo "⚠️  Adicionando configuração de shared-tools..."
    # Modificar config.yaml (fazer backup)
    cp "$CONTINUE_CONFIG" "$CONTINUE_CONFIG.bak"
    echo "   (backup criado: $CONTINUE_CONFIG.bak)"
fi

# ============================================================
# 2. PyCharm Configuration
# ============================================================

echo ""
echo "📝 Configurando Continue.dev para PyCharm..."

# Locais possíveis de config do PyCharm
declare -a PYCHARM_CONFIG_PATHS=(
    "$HOME/.idea/continue/config.yaml"
    "$HOME/.continue-pycharm/config.yaml"
    "$HOME/PycharmProjects/.continue/config.yaml"
)

PYCHARM_CONFIG_FOUND=0

for config_path in "${PYCHARM_CONFIG_PATHS[@]}"; do
    if [ -f "$config_path" ]; then
        echo "✅ Encontrado: $config_path"
        PYCHARM_CONFIG_FOUND=1
        
        if grep -q "shared-tools" "$config_path"; then
            echo "✅ PyCharm já está configurado com shared-tools"
        else
            echo "⚠️  Atualizando configuração..."
            # Fazer backup
            cp "$config_path" "$config_path.bak"
            echo "   (backup criado: $config_path.bak)"
        fi
        break
    fi
done

if [ $PYCHARM_CONFIG_FOUND -eq 0 ]; then
    echo "⚠️  Nenhum config do PyCharm encontrado."
    echo "   Criando em: ~/.idea/continue/config.yaml"
    mkdir -p "$HOME/.idea/continue"
    
    # Copiar config do VS Code
    cp "$CONTINUE_CONFIG" "$HOME/.idea/continue/config.yaml"
    echo "✅ Config do VS Code copiada para PyCharm"
fi

# ============================================================
# 3. Verifiquei da API
# ============================================================

echo ""
echo "🔍 Verificando Shared Tool Executor API..."

API_URL="http://localhost:8503/llm-tools/health"

if curl -s "$API_URL" | grep -q "ok"; then
    echo "✅ API está rodando em $API_URL"
else
    echo "⚠️  API não respondeu em $API_URL"
    echo "   Inicie com: python3 llm_tool_client.py"
    echo "   (ou) cd /path/to/shared-auto-dev && uvicorn specialized_agents.api:app --port 8503"
fi

# ============================================================
# 4. Verificar Ollama
# ============================================================

echo ""
echo "🔍 Verificando Ollama..."

OLLAMA_URL="http://192.168.15.2:11434/api/tags"

if curl -s "$OLLAMA_URL" | grep -q '"models"'; then
    echo "✅ Ollama está rodando em http://192.168.15.2:11434"
    
    # Listar modelos disponíveis
    echo "   Modelos disponíveis:"
    curl -s "$OLLAMA_URL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for model in data.get('models', [])[:5]:
    print(f\"     - {model.get('model', model.get('name', '?'))}\")
" 2>/dev/null || echo "     (não foi possível listar)"
else
    echo "❌ Ollama não respondeu em $OLLAMA_URL"
    echo "   Inicie no homelab: ollama serve"
fi

# ============================================================
# 5. Resumo
# ============================================================

echo ""
echo "========================================"
echo "✅ Setup concluído!"
echo ""
echo "📌 Próximos passos:"
echo ""
echo "VS Code:"
echo "  1. Instale extensão: Continue (marketplace)"
echo "  2. Abra Continue: Ctrl+Shift+V"
echo "  3. Digite: /health"
echo ""
echo "PyCharm:"
echo "  1. Instale plugin: Continue (marketplace)"
echo "  2. Tools → Continue"
echo "  3. Digite: /health"
echo ""
echo "Teste a execução real de comandos:"
echo "  - /docker"
echo "  - /btc"
echo "  - /logs"
echo ""
echo "Documentação: CONTINUE_SETUP.md"
echo "========================================"
