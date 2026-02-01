#!/usr/bin/env python3
"""Script para configurar DEPLOY_SSH_KEY no GitHub"""

import base64
import os
import requests
from nacl import encoding, public

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "eddiejdi/eddie-auto-dev")

if not GITHUB_TOKEN:
    print("Erro: GITHUB_TOKEN não definido")
    exit(1)

# Chave SSH para deploy
SSH_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACAB3muvlOiBU3Z5wq5sdWvBbP2vuQ/4XiiUtIQWS90dGgAAAJgSe+DNEnvg
zQAAAAtzc2gtZWQyNTUxOQAAACAB3muvlOiBU3Z5wq5sdWvBbP2vuQ/4XiiUtIQWS90dGg
AAAEABpuJ/hPma6jxUaHEejduN4CIT+F32GYhCo7wIFfW0XAHea6+U6IFTdnnCrmx1a8Fs
/a+5D/heKJS0hBZL3R0aAAAAEWdpdGh1Yi1kZXBsb3kta2V5AQIDBA==
-----END OPENSSH PRIVATE KEY-----"""


def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


# Headers
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# Obter public key
print("🔐 Obtendo public key do repositório...")
resp = requests.get(
    f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=headers
)
key_data = resp.json()
key_id = key_data["key_id"]
public_key = key_data["key"]

print(f"   Key ID: {key_id}")

# Encriptar
print("🔒 Encriptando chave SSH...")
encrypted = encrypt(public_key, SSH_KEY)

# Criar secret
print("📤 Enviando para GitHub...")
data = {"encrypted_value": encrypted, "key_id": key_id}

resp = requests.put(
    f"https://api.github.com/repos/{REPO}/actions/secrets/DEPLOY_SSH_KEY",
    headers=headers,
    json=data,
)

if resp.status_code in [201, 204]:
    print("✅ Secret DEPLOY_SSH_KEY configurado com sucesso!")
else:
    print(f"❌ Erro: {resp.status_code} - {resp.text}")

print()
print("📋 Agora adicione a chave pública no servidor 192.168.15.2:")
print()
print(
    "ssh homelab@192.168.15.2 'mkdir -p ~/.ssh && echo \"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAHea6+U6IFTdnnCrmx1a8Fs/a+5D/heKJS0hBZL3R0a github-deploy-key\" >> ~/.ssh/authorized_keys'"
)
