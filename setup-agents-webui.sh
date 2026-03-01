#!/bin/bash
# Script para ativar e testar a integração de agentes com WebUI

set -e

REPO_DIR="/home/edenilson/eddie-auto-dev"
API_PORT=8503
HOMELAB_HOST="192.168.15.2"
WEBUI_HOST="192.168.15.2:3000"

echo "════════════════════════════════════════════════════════"
echo "🤖 Ativando integração de Agentes no WebUI"
echo "════════════════════════════════════════════════════════"
echo ""

# 1. Verificar dependências
echo "📦 Verificando dependências..."
cd "$REPO_DIR"

# Verificar se agents_webui_bridge.py foi criado
if [ ! -f "specialized_agents/agents_webui_bridge.py" ]; then
    echo "❌ agents_webui_bridge.py não encontrado!"
    exit 1
fi
echo "✅ agents_webui_bridge.py OK"

# Verificar se api.py foi atualizado
if grep -q "agents_webui_bridge" specialized_agents/api.py; then
    echo "✅ api.py atualizado com endpoints de agentes"
else
    echo "⚠️  api.py pode precisar de reload"
fi

# Verificar se openwebui_integration.py foi atualizado
if grep -q "python_agent" openwebui_integration.py; then
    echo "✅ openwebui_integration.py atualizado com perfis de agentes"
else
    echo "⚠️  openwebui_integration.py pode precisar de reload"
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "✨ Configuração Completa!"
echo "════════════════════════════════════════════════════════"
echo ""

echo "📍 Próximos Passos:"
echo ""
echo "1️⃣  REINICIAR API (para carregar os novos endpoints)"
echo "   $ systemctl restart specialized-agents-api"
echo "   OU (desenvolvimento):"
echo "   $ source .venv/bin/activate"
echo "   $ uvicorn specialized_agents.api:app --reload --port 8503"
echo ""

echo "2️⃣  VERIFICAR AGENTES DISPONÍVEIS"
echo "   $ curl http://localhost:8503/agents | jq"
echo ""

echo "3️⃣  LISTAR MODELOS OpenWebUI (após restart)"
echo "   $ curl http://localhost:8503/v1/models | jq"
echo ""

echo "4️⃣  (OPCIONAL) REGISTRAR AGENTES NO WEBUI"
echo "   $ python3 register_agents_webui.py \\"
echo "     --webui-url http://$WEBUI_HOST \\"
echo "     --api-url http://localhost:$API_PORT"
echo ""

echo "5️⃣  USAR VIA API (após restart)"
echo "   $ curl -X POST http://localhost:$API_PORT/v1/chat/completions \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{"
echo "       \"model\": \"agent-python\","
echo "       \"messages\": [{\"role\": \"user\", \"content\": \"Oi\"}]"
echo "     }'"
echo ""

echo "════════════════════════════════════════════════════════"
echo "📚 Documentação"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Leia: AGENTS_WEBUI_INTEGRATION.md para:"
echo "  • Exemplos detalhados de uso"
echo "  • Integração com LangChain, VSCode, etc"
echo "  • Solução de problemas"
echo "  • Configuração avançada"
echo ""

echo "════════════════════════════════════════════════════════"
echo "🎯 Agentes Disponíveis"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Agentes de Linguagem (8):"
echo "  🐍  agent-python       - Python Expert"
echo "  📘  agent-javascript   - JavaScript Expert"
echo "  🔷  agent-typescript   - TypeScript Expert"
echo "  🐹  agent-go           - Go Expert"
echo "  🦀  agent-rust         - Rust Expert"
echo "  ☕  agent-java         - Java Expert"
echo "  #   agent-csharp       - C# Expert"
echo "  🔗  agent-php          - PHP Expert"
echo ""

echo "Agentes Especializados:"
echo "  🔄  BPM Diagrams       - Criador de diagramas BPMN"
echo "  📝  Confluence Docs    - Gerador de documentação"
echo "  🔒  Security Scanner   - Análise de vulnerabilidades"
echo "  📊  Data Pipelines     - ETL e processamento"
echo "  ⚡  Load Testing       - Performance testing"
echo ""

echo "════════════════════════════════════════════════════════"
echo "🌐 URLs Importantes"
echo "════════════════════════════════════════════════════════"
echo ""
echo "API Local:        http://localhost:$API_PORT"
echo "OpenWebUI:        http://$WEBUI_HOST"
echo "API Docs:         http://localhost:$API_PORT/docs"
echo "Homelab API:      http://$HOMELAB_HOST:$API_PORT"
echo ""

echo "════════════════════════════════════════════════════════"
echo "✅ Setup concluído com sucesso!"
echo "════════════════════════════════════════════════════════"
