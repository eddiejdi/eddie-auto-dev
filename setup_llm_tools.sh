#!/bin/bash
# Setup LLM Tool Executor - Criar modelo customizado e testar

set -e

echo "========================================="
echo "🚀 LLM Tool Executor Setup"
echo "========================================="

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verificar se Ollama está rodando
echo -e "${BLUE}[1/5]${NC} Verificando Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama não está rodando em localhost:11434${NC}"
    echo "    Inicie com: ollama serve"
    exit 1
fi
echo -e "${GREEN}✓${NC} Ollama detectado"

# Verificar se API está rodando
echo -e "${BLUE}[2/5]${NC} Verificando API..."
if ! curl -s http://localhost:8503/llm-tools/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  API não está rodando em localhost:8503${NC}"
    echo "    Inicie com: uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503"
    exit 1
fi
echo -e "${GREEN}✓${NC} API detectada"

# Criar modelo customizado
echo -e "${BLUE}[3/5]${NC} Criando modelo customizado 'shared-tools'..."
if [ -f "./models/Modelfile.shared-tools" ]; then
    cd models
    if ollama show shared-tools > /dev/null 2>&1; then
        echo -e "${YELLOW}  Modelo já existe${NC}"
    else
        echo "  Construindo modelo..."
        ollama create shared-tools -f Modelfile.shared-tools
        echo -e "${GREEN}✓${NC} Modelo 'shared-tools' criado"
    fi
    cd ..
else
    echo -e "${YELLOW}  Arquivo Modelfile.shared-tools não encontrado${NC}"
fi

# Testar API
echo -e "${BLUE}[4/5]${NC} Testando endpoints da API..."

# Health check
echo "  Verificando health..."
HEALTH=$(curl -s http://localhost:8503/llm-tools/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓${NC} Health check OK"
else
    echo -e "${YELLOW}⚠️  Health check falhou${NC}"
fi

# Available tools
echo "  Listando ferramentas..."
TOOLS=$(curl -s http://localhost:8503/llm-tools/available | jq '.tools | length')
echo -e "${GREEN}✓${NC} $TOOLS ferramentas disponíveis"

# Test shell_exec
echo "  Testando shell_exec..."
SHELL_TEST=$(curl -s -X POST http://localhost:8503/llm-tools/exec-shell \
  -H 'Content-Type: application/json' \
  -d '{"command":"pwd"}')

if echo "$SHELL_TEST" | grep -q "success"; then
    echo -e "${GREEN}✓${NC} shell_exec funcionando"
else
    echo -e "${YELLOW}⚠️  shell_exec falhou${NC}"
fi

# Criar script de teste interativo
echo -e "${BLUE}[5/5]${NC} Criando scripts de teste..."

# Script para testar
cat > test_llm_tools.sh << 'EOF'
#!/bin/bash
echo "🔧 Testando LLM Tool Executor"
echo ""
echo "1️⃣  Listar ferramentas disponíveis:"
curl -s http://localhost:8503/llm-tools/available | jq '.tools[] | {name: .name, description: .description}'

echo ""
echo "2️⃣  Executar comando (pwd):"
curl -s -X POST http://localhost:8503/llm-tools/exec-shell \
  -H 'Content-Type: application/json' \
  -d '{"command":"pwd"}' | jq '.'

echo ""
echo "3️⃣  Obter informações do sistema:"
curl -s http://localhost:8503/llm-tools/system-info | jq '.system'

echo ""
echo "4️⃣  Listar home:"
curl -s -X POST http://localhost:8503/llm-tools/list-directory \
  -H 'Content-Type: application/json' \
  -d '{"dirpath":"/home","recursive":false}' | jq '.entries | length'

echo ""
echo "✅ Testes básicos concluídos!"
EOF

chmod +x test_llm_tools.sh

echo -e "${GREEN}✓${NC} Script de teste criado: test_llm_tools.sh"

# Resumo
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ Setup Completo!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${BLUE}Próximas Etapas:${NC}"
echo ""
echo "1. Usar o cliente Python interativo:"
echo "   python3 llm_tool_client.py --interactive --model shared-tools"
echo ""
echo "2. Ou fazer uma query direta:"
echo "   python3 llm_tool_client.py 'qual é o status do git?' --model shared-tools"
echo ""
echo "3. Testar endpoints API:"
echo "   ./test_llm_tools.sh"
echo ""
echo "4. Ler documentação:"
echo "   cat docs/LLM_TOOL_EXECUTOR.md"
echo ""
echo -e "${YELLOW}⚠️  Certifique-se que:${NC}"
echo "  - Ollama está rodando: ollama serve"
echo "  - API está ativa: uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503"
echo "  - Modelo shared-tools foi criado: ollama list"
echo ""
