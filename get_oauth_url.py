#!/usr/bin/env python3
"""Gerar URL OAuth para autorização do Gmail."""
import json
import subprocess
import sys
from pathlib import Path

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_DB = "/var/lib/shared/secrets_agent/audit.db"

print("📥 Obtendo credenciais do Secrets Agent...\n")

cmd = [
    "ssh", f"homelab@{SECRETS_AGENT_HOST}",
    f"""python3 - <<'PY'
import sqlite3, base64, json
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='google/oauth_client_installed' AND field='credentials_json'")
row = c.fetchone()
conn.close()
if row:
    try:
        data = json.loads(base64.b64decode(row[0]).decode())
        print(json.dumps(data))
    except:
        print(json.dumps(json.loads(row[0])))
PY"""
]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
if res.returncode != 0:
    print(f"❌ Erro ao obter credenciais: {res.stderr}")
    sys.exit(1)

try:
    creds_json = json.loads(res.stdout)
except:
    print(f"❌ Erro ao parsear credenciais")
    sys.exit(1)

client_id = creds_json["installed"]["client_id"]
client_secret = creds_json["installed"]["client_secret"]

# OAuth URL parameters
base_url = "https://accounts.google.com/o/oauth2/auth"
params = {
    'response_type': 'code',
    'client_id': client_id,
    'redirect_uri': 'http://localhost:8080/',
    'scope': ' '.join([
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/drive',
    ]),
    'access_type': 'offline',
    'prompt': 'consent',
}

from urllib.parse import urlencode
auth_url = f"{base_url}?{urlencode(params)}"

print("="*70)
print("✅ ACESSE A URL ABAIXO NO SEU NAVEGADOR:")
print("="*70)
print(f"\n{auth_url}\n")
print("="*70)
print("\n1️⃣  Clique no link acima (ou copie e cole no navegador)")
print("2️⃣  Faça login no Gmail (se necessário)")
print("3️⃣  Clique em 'Permitir' para autorizar os escopos")
print("4️⃣  Depois você será redirecionado para uma página com a URL contendo 'code='")
print("5️⃣  Procure por 'code=...' na URL final")
print("6️⃣  Cole o código abaixo\n")

auth_code = input("🔑 Cola o CÓDIGO DE AUTORIZAÇÃO (code=...): ").strip()

if not auth_code:
    print("❌ Código não fornecido!")
    sys.exit(1)

# Now exchange code for token
import requests

print(f"\n🔄 Trocando código por token...")

token_url = "https://oauth2.googleapis.com/token"
data = {
    'code': auth_code,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': 'http://localhost:8080/',
    'grant_type': 'authorization_code',
}

res = requests.post(token_url, data=data)
if res.status_code != 200:
    print(f"❌ Erro ao obter token: {res.json()}")
    sys.exit(1)

token_resp = res.json()
print("✅ Token obtido com sucesso!")
print(f"   access_token: {token_resp['access_token'][:30]}...")
print(f"   refresh_token: {token_resp.get('refresh_token', 'N/A')[:30] if token_resp.get('refresh_token') else 'N/A'}...")

# Save to Secrets Agent
print("\n💾 Salvando no Secrets Agent...")
import base64

token_json = json.dumps({
    'token': token_resp['access_token'],
    'refresh_token': token_resp.get('refresh_token'),
    'token_uri': 'https://oauth2.googleapis.com/token',
    'client_id': client_id,
    'client_secret': client_secret,
    'scopes': [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/drive',
    ],
})

token_b64 = base64.b64encode(token_json.encode()).decode()

cmd = [
    "ssh", f"homelab@{SECRETS_AGENT_HOST}",
    f"""python3 - <<'PY'
import sqlite3, base64
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
c.execute("INSERT OR REPLACE INTO secrets_store (name, field, value) VALUES (?, ?, ?)",
          ('google/gmail_token', 'token_json', '{token_b64}'))
conn.commit()
conn.close()
print('OK')
PY"""
]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
if "OK" in res.stdout:
    print("✅ Token salvo no Secrets Agent!")
else:
    print(f"❌ Erro ao salvar: {res.stderr}")
    sys.exit(1)

print("\n" + "="*70)
print("✅ SUCESSO! Gmail API configurado!")
print("="*70)
print("\n🎉 Agora você pode enviar emails!")
print("\nExecute um dos comandos:")
print("  • python3 send_via_curl.py")
print("  • python3 apply_real_job.py")
