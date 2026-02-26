#!/usr/bin/env python3
"""
Gera uma API key forte e armazena no Secrets Agent como 'ollama/api_key'.
Necessita: SECRETS_AGENT_URL e SECRETS_AGENT_API_KEY exportados no ambiente.
"""
import os
import secrets
import sys
import urllib.parse
import requests

SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://localhost:8088")
SECRETS_AGENT_API_KEY = os.environ.get("SECRETS_AGENT_API_KEY")

if not SECRETS_AGENT_API_KEY:
    print("[ERRO] Defina SECRETS_AGENT_API_KEY no ambiente.", file=sys.stderr)
    sys.exit(1)

# 1. Gerar chave forte
api_key = secrets.token_urlsafe(48)

# 2. Montar payload
payload = {
    "name": "ollama/api_key",
    "value": api_key,
    "field": "password",
    "notes": "Ollama API key gerada automaticamente"
}

# 3. Enviar para o Secrets Agent
resp = requests.post(
    f"{SECRETS_AGENT_URL}/secrets",
    headers={
        "Content-Type": "application/json",
        "X-API-KEY": SECRETS_AGENT_API_KEY
    },
    json=payload
)
if resp.status_code != 200:
    print(f"[ERRO] Falha ao armazenar secret: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(2)
print("[OK] API key armazenada com sucesso.")

# 4. Verificar leitura
enc_name = urllib.parse.quote("ollama/api_key", safe="")
verify = requests.get(
    f"{SECRETS_AGENT_URL}/secrets/local/{enc_name}?field=password",
    headers={"X-API-KEY": SECRETS_AGENT_API_KEY}
)
if verify.status_code == 200:
    print("[OK] Leitura verificada:", verify.json())
else:
    print(f"[ERRO] Falha ao ler secret: {verify.status_code} {verify.text}", file=sys.stderr)
    sys.exit(3)
