#!/bin/bash
# Script de teste completo do Eddie Copilot
# Testa todas as funcionalidades: autocomplete, chat, conexões

echo "=========================================="
echo "🧪 TESTES EDDIE COPILOT"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

OLLAMA_URL="http://192.168.15.2:11434"
LOCAL_MODEL="qwen2.5-coder:1.5b"
REMOTE_URL="http://192.168.15.2:3000"

# Teste 1: Conexão Ollama Local
echo -e "${YELLOW}[1/5] Testando conexão Ollama local...${NC}"
if curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama local conectado ($OLLAMA_URL)${NC}"
else
    echo -e "${RED}❌ Ollama local não disponível${NC}"
    exit 1
fi

# Teste 2: Modelo disponível
echo -e "\n${YELLOW}[2/5] Verificando modelo $LOCAL_MODEL...${NC}"
if curl -s "$OLLAMA_URL/api/tags" | grep -q "$LOCAL_MODEL"; then
    echo -e "${GREEN}✅ Modelo $LOCAL_MODEL disponível${NC}"
else
    echo -e "${RED}❌ Modelo $LOCAL_MODEL não encontrado${NC}"
    echo "   Modelos disponíveis:"
    curl -s "$OLLAMA_URL/api/tags" | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(['   - ' + m['name'] for m in d.get('models',[])]))"
fi

# Teste 3: Autocomplete
echo -e "\n${YELLOW}[3/5] Testando autocomplete...${NC}"
PROMPT="def fibonacci(n):\n    "
RESPONSE=$(curl -s "$OLLAMA_URL/api/generate" \
    -d "{
        \"model\": \"$LOCAL_MODEL\",
        \"prompt\": \"$PROMPT\",
        \"stream\": false,
        \"options\": {
            \"num_predict\": 100,
            \"temperature\": 0.2
        }
    }" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','ERROR')[:200])" 2>/dev/null)

if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "ERROR" ]; then
    echo -e "${GREEN}✅ Autocomplete funcionando${NC}"
    echo "   Prompt: def fibonacci(n):"
    echo "   Resposta: ${RESPONSE:0:100}..."
else
    echo -e "${RED}❌ Autocomplete falhou${NC}"
fi

# Teste 4: Chat
echo -e "\n${YELLOW}[4/5] Testando chat...${NC}"
CHAT_RESPONSE=$(curl -s "$OLLAMA_URL/api/chat" \
    -d "{
        \"model\": \"$LOCAL_MODEL\",
        \"messages\": [
            {\"role\": \"user\", \"content\": \"Explique em uma frase o que é Python.\"}
        ],
        \"stream\": false,
        \"options\": {
            \"num_predict\": 100
        }
    }" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',{}).get('content','ERROR')[:200])" 2>/dev/null)

if [ -n "$CHAT_RESPONSE" ] && [ "$CHAT_RESPONSE" != "ERROR" ]; then
    echo -e "${GREEN}✅ Chat funcionando${NC}"
    echo "   Pergunta: Explique em uma frase o que é Python."
    echo "   Resposta: ${CHAT_RESPONSE:0:150}..."
else
    echo -e "${RED}❌ Chat falhou${NC}"
fi

# Teste 5: Servidor Remoto (Open WebUI)
echo -e "\n${YELLOW}[5/5] Testando servidor remoto...${NC}"
if curl -s --connect-timeout 5 "$REMOTE_URL/health" | grep -q "OK"; then
    echo -e "${GREEN}✅ Servidor remoto acessível ($REMOTE_URL)${NC}"
    echo -e "${YELLOW}   ⚠️  API Key não configurada - funcionalidades remotas desativadas${NC}"
    echo "   Para ativar: Abra VS Code Settings > Eddie Copilot > API Key"
else
    echo -e "${YELLOW}⚠️ Servidor remoto não acessível${NC}"
fi

echo ""
echo "=========================================="
echo "📊 RESUMO"
echo "=========================================="
echo ""
echo "Para usar o Eddie Copilot:"
echo "1. Recarregue o VS Code (Ctrl+Shift+P > Developer: Reload Window)"
echo "2. Abra um arquivo Python ou JavaScript"
echo "3. Digite código e aguarde sugestões (Alt+\\ para forçar)"
echo "4. Use Ctrl+Shift+I para abrir o chat"
echo "5. Clique em 'Eddie [L]' na barra de status para verificar conexão"
echo ""
echo -e "${GREEN}✅ Testes concluídos!${NC}"
