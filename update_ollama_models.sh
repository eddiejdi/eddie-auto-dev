#!/bin/bash
# Script para atualizar modelos do Ollama com conhecimento de relatórios

OLLAMA_HOST="${OLLAMA_HOST:-${HOMELAB_HOST:-localhost}:11434}"
MODELS_DIR="/home/homelab/myClaude"

echo "=== Atualizando modelos Ollama ==="
echo "Host: $OLLAMA_HOST"
echo ""

# Verificar se Ollama está acessível
if ! curl -s "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "❌ Ollama não está acessível em $OLLAMA_HOST"
    exit 1
fi

echo "✅ Ollama acessível"
echo ""

# Função para criar modelo via API
create_model() {
    local name=$1
    local modelfile=$2
    
    echo "📦 Criando modelo: $name"
    
    # Ler conteúdo do Modelfile
    local content=$(cat "$modelfile")
    
    # Criar JSON com escape adequado
    python3 << EOF
import json
import requests

modelfile_content = open("$modelfile").read()
data = {
    "name": "$name",
    "modelfile": modelfile_content
}

response = requests.post(
    "http://$OLLAMA_HOST/api/create",
    json=data,
    stream=True
)

for line in response.iter_lines():
    if line:
        try:
            status = json.loads(line)
            if "status" in status:
                print(f"  {status['status']}")
        except:
            print(f"  {line.decode()}")

if response.status_code == 200:
    print(f"✅ Modelo {name} criado com sucesso!")
else:
    print(f"❌ Erro ao criar {name}: {response.status_code}")
EOF
    
    echo ""
}

# Atualizar shared-assistant
if [ -f "$MODELS_DIR/shared-assistant-v2.Modelfile" ]; then
    create_model "shared-assistant" "$MODELS_DIR/shared-assistant-v2.Modelfile"
fi

# Atualizar shared-whatsapp
if [ -f "$MODELS_DIR/shared-whatsapp-v2.Modelfile" ]; then
    create_model "shared-whatsapp" "$MODELS_DIR/shared-whatsapp-v2.Modelfile"
fi

echo ""
echo "=== Listando modelos atuais ==="
curl -s "http://$OLLAMA_HOST/api/tags" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for model in data.get('models', []):
    name = model.get('name', '')
    size = model.get('size', 0) / (1024**3)
    print(f'  • {name} ({size:.1f} GB)')
"

echo ""
echo "✅ Atualização completa!"
