#!/bin/bash
# Script para configurar a chave SSH de deploy como secret

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO="${GITHUB_REPO:-eddiejdi/eddie-auto-dev}"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Erro: GITHUB_TOKEN não definido"
    exit 1
fi
SECRET_NAME="DEPLOY_SSH_KEY"

# Ler a chave privada
SSH_KEY=$(cat /home/home-lab/.ssh/deploy_key)

echo "🔐 Obtendo public key do repositório..."

# Obter public key do repositório
key_response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    "https://api.github.com/repos/$REPO/actions/secrets/public-key")

key_id=$(echo "$key_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['key_id'])")
public_key=$(echo "$key_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")

echo "🔒 Encriptando chave SSH..."

# Encriptar o secret usando Python
encrypted=$(python3 << EOF
from base64 import b64encode
from nacl import encoding, public

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

ssh_key = """$SSH_KEY"""
print(encrypt("$public_key", ssh_key))
EOF
)

echo "📤 Enviando para GitHub..."

# Criar o secret
result=$(curl -s -X PUT \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$REPO/actions/secrets/$SECRET_NAME" \
    -d "{\"encrypted_value\":\"$encrypted\",\"key_id\":\"$key_id\"}")

echo "✅ Secret DEPLOY_SSH_KEY configurado!"
echo ""
echo "📋 Chave pública para adicionar no servidor (authorized_keys):"
echo ""
cat /home/home-lab/.ssh/deploy_key.pub
echo ""
echo "🖥️  Execute no servidor 192.168.15.2:"
echo "   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAHea6+U6IFTdnnCrmx1a8Fs/a+5D/heKJS0hBZL3R0a github-deploy-key' >> ~/.ssh/authorized_keys"
