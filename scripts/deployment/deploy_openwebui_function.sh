#!/bin/bash
# Script de Deploy - Agent Coordinator Function para Open WebUI
# Uso: ./deploy_openwebui_function.sh

set -e

FUNCTION_FILE="/home/homelab/myClaude/openwebui_agent_coordinator_function.py"
OPEN_WEBUI_URL="http://localhost:3000"

echo "=========================================="
echo "  Deploy Agent Coordinator Function"
echo "=========================================="
echo ""

# Verificar se o arquivo existe
if [ ! -f "$FUNCTION_FILE" ]; then
    echo "❌ Arquivo não encontrado: $FUNCTION_FILE"
    exit 1
fi
echo "✅ Arquivo encontrado: $FUNCTION_FILE"

# Verificar se Open WebUI está rodando
if ! curl -s "$OPEN_WEBUI_URL/api/version" > /dev/null; then
    echo "❌ Open WebUI não está acessível em $OPEN_WEBUI_URL"
    exit 1
fi
VERSION=$(curl -s "$OPEN_WEBUI_URL/api/version" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))")
echo "✅ Open WebUI versão $VERSION está rodando"

# Exibir conteúdo do arquivo
echo ""
echo "📄 Função a ser instalada:"
head -10 "$FUNCTION_FILE"
echo "..."
echo ""

# Instruções de instalação manual
echo "=========================================="
echo "  INSTRUÇÕES DE INSTALAÇÃO MANUAL"
echo "=========================================="
echo ""
echo "Como o Open WebUI requer autenticação para a API,"
echo "siga estes passos para instalar a função:"
echo ""
echo "1️⃣  Acesse: PUBLIC_TUNNEL_URL (não configurado)"
echo ""
echo "2️⃣  Faça login com sua conta Google"
echo ""
echo "3️⃣  Clique no seu avatar (canto superior direito)"
echo "    → Selecione 'Admin Panel' ou 'Painel de Administração'"
echo ""
echo "4️⃣  No menu lateral, vá em 'Functions' (ou 'Funções')"
echo ""
echo "5️⃣  Clique em '+ Create Function' ou 'Nova Função'"
echo ""
echo "6️⃣  Cole o código do arquivo:"
echo "    📁 $FUNCTION_FILE"
echo ""
echo "7️⃣  Clique em 'Save' (Salvar)"
echo ""
echo "8️⃣  Ative o toggle para habilitar a função"
echo ""
echo "=========================================="
echo ""
echo "📋 Para copiar o código, execute:"
echo "   cat $FUNCTION_FILE | xclip -selection clipboard"
echo ""
echo "   Ou acesse o arquivo diretamente no servidor."
echo ""
echo "=========================================="
echo "  COMANDOS DISPONÍVEIS APÓS INSTALAÇÃO"
echo "=========================================="
echo ""
echo "🚀 Desenvolvimento:"
echo "   /projeto <descrição>  - Inicia análise de requisitos"
echo "   /gerar                - Gera código"
echo "   /requisitos           - Mostra requisitos"
echo "   /cancelar             - Cancela projeto"
echo ""
echo "🐛 Suporte:"
echo "   /bug <descrição>      - Reporta problema"
echo "   /reportar <descrição> - Mesmo que /bug"
echo ""
echo "⚡ Execução:"
echo "   /exec <código>        - Executa código Python"
echo ""
echo "🔍 Busca:"
echo "   /rag <query>          - Busca documentação"
echo ""
echo "📊 Sistema:"
echo "   /agents               - Lista agentes"
echo "   /status               - Status do sistema"
echo "   /help                 - Ajuda"
echo ""
echo "=========================================="
echo "  Deploy preparado! Instale manualmente."
echo "=========================================="
