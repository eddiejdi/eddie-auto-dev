#!/bin/bash
# Script para instalar função no Open WebUI via API

WEBUI_URL="http://192.168.15.2:3000"
EMAIL="edenilson.adm@gmail.com"
PASSWORD="Eddie@2026"

echo "=== Instalando Agent Coordinator Function no Open WebUI ==="
echo ""

# 1. Fazer login e obter token
echo "1. Fazendo login..."
LOGIN_RESPONSE=$(curl -s -X POST "$WEBUI_URL/api/v1/auths/signin" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Erro ao obter token. Resposta: $LOGIN_RESPONSE"
    exit 1
fi

echo "Login bem-sucedido!"
echo ""

# 2. Ler o arquivo da função
FUNCTION_FILE="/home/homelab/myClaude/openwebui_agent_coordinator_function.py"
if [ ! -f "$FUNCTION_FILE" ]; then
    echo "Arquivo da função não encontrado: $FUNCTION_FILE"
    exit 1
fi

FUNCTION_CONTENT=$(cat "$FUNCTION_FILE")
echo "Função carregada ($(echo "$FUNCTION_CONTENT" | wc -l) linhas)"
echo ""

# 3. Escapar o conteúdo para JSON
ESCAPED_CONTENT=$(echo "$FUNCTION_CONTENT" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")

# 4. Verificar funções existentes
echo "2. Verificando funções existentes..."
EXISTING=$(curl -s -X GET "$WEBUI_URL/api/v1/functions/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "Funções: $(echo "$EXISTING" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null)"

# 5. Criar payload
FUNCTION_ID="agent_coordinator"
FUNCTION_NAME="Agent Coordinator"
FUNCTION_DESC="Integra Open WebUI com Agent Coordinator"

# 6. Criar a função
echo ""
echo "3. Criando função..."

PAYLOAD=$(cat <<EOFPAYLOAD
{
  "id": "$FUNCTION_ID",
  "name": "$FUNCTION_NAME",
  "meta": {
    "description": "$FUNCTION_DESC"
  },
  "content": $ESCAPED_CONTENT
}
EOFPAYLOAD
)

RESULT=$(curl -s -X POST "$WEBUI_URL/api/v1/functions/create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "Resposta: $RESULT"
echo ""

# 7. Verificar resultado
if echo "$RESULT" | grep -q "agent_coordinator"; then
    echo "Função criada com sucesso!"
    
    # 8. Habilitar a função
    echo ""
    echo "4. Habilitando função..."
    curl -s -X POST "$WEBUI_URL/api/v1/functions/id/$FUNCTION_ID/toggle" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json"
    echo ""
else
    echo "Verifique no Admin Panel -> Functions"
fi

echo ""
echo "========================================"
echo "Instalação concluída!"
echo "Acesse: $WEBUI_URL"
echo "========================================"
