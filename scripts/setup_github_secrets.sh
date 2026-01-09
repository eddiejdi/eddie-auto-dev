#!/bin/bash
# Script para configurar GitHub Secrets

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO="${GITHUB_REPO:-eddiejdi/eddie-auto-dev}"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Erro: GITHUB_TOKEN não definido"
    exit 1
fi

# Função para criar/atualizar secret
create_secret() {
    local secret_name="$1"
    local secret_value="$2"
    
    echo "🔐 Criando secret: $secret_name"
    
    # Obter public key do repositório
    local key_response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$REPO/actions/secrets/public-key")
    
    local key_id=$(echo "$key_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['key_id'])")
    local public_key=$(echo "$key_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")
    
    # Encriptar o secret usando Python
    local encrypted=$(python3 << EOF
from base64 import b64encode
from nacl import encoding, public

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

print(encrypt("$public_key", """$secret_value"""))
EOF
)
    
    # Criar o secret
    curl -s -X PUT \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$REPO/actions/secrets/$secret_name" \
        -d "{\"encrypted_value\":\"$encrypted\",\"key_id\":\"$key_id\"}"
    
    echo " ✅ $secret_name configurado"
}

echo "📦 Instalando dependência PyNaCl..."
pip install pynacl -q

echo ""
echo "🔧 Configurando GitHub Secrets para CI/CD..."
echo ""

# Secrets necessários
create_secret "TELEGRAM_BOT_TOKEN" "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
create_secret "TELEGRAM_CHAT_ID" "948686300"

echo ""
echo "⚠️  ATENÇÃO: Configure manualmente o DEPLOY_SSH_KEY"
echo "   Execute o setup_deploy_server.sh primeiro para gerar a chave SSH"
echo "   Depois adicione a chave privada como secret DEPLOY_SSH_KEY"
echo ""
echo "✅ Secrets configurados!"
echo ""
echo "📋 Para ver os secrets: https://github.com/$REPO/settings/secrets/actions"
