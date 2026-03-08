#!/usr/bin/env python3
"""
Obter novo token Gmail - tudo em um script, rápido.
"""
import json
import subprocess
import sys
import base64

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_DB = "/var/lib/shared/secrets_agent/audit.db"

print("="*70)
print("🔄 CONFIGURANDO OAUTH GMAIL")
print("="*70 + "\n")

# Get credentials
print("📥 Obtendo credenciais...")
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
try:
    creds_json = json.loads(res.stdout)
except:
    print(f"❌ Erro ao obter credenciais")
    sys.exit(1)

client_id = creds_json["installed"]["client_id"]
client_secret = creds_json["installed"]["client_secret"]

# Generate auth URL
from urllib.parse import urlencode

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

auth_url = f"{base_url}?{urlencode(params)}"

print("📋 AUTORIZAR GMAIL:")
print("="*70)
print(f"\n{auth_url}\n")
print("="*70)
print("\n✅ Copie a URL acima, abra no navegador, autorize, e copie o CÓDIGO")
print("💡 O código aparece na URL como: code=XXXXXX\n")

# Get code from user
auth_code = input("🔑 Cole o CÓDIGO (só a parte depois de 'code='): ").strip()
if not auth_code:
    print("❌ Código não fornecido!")
    sys.exit(1)

print(f"\n🔄 Trocando código por token...")

import requests

token_url = "https://oauth2.googleapis.com/token"
data = {
    'code': auth_code,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': 'http://localhost:8080/',
    'grant_type': 'authorization_code',
}

try:
    res = requests.post(token_url, data=data, timeout=30)
    
    if res.status_code != 200:
        resp_json = res.json()
        error = resp_json.get('error', 'Unknown')
        desc = resp_json.get('error_description', '')
        print(f"❌ Erro: {error}")
        if error == "invalid_grant":
            print("   💡 O código expirou (válido por 10 minutos). Tente novamente rapidinho!")
        else:
            print(f"   Descrição: {desc}")
        sys.exit(1)
    
    token_resp = res.json()
    
except Exception as e:
    print(f"❌ Erro na requisição: {e}")
    sys.exit(1)

print("✅ Token obtido!")
print(f"   access_token: {token_resp['access_token'][:40]}...")
print(f"   refresh_token: {token_resp.get('refresh_token', 'N/A')[:40] if token_resp.get('refresh_token') else 'N/A'}...")

# Save to agent
print("\n💾 Salvando token no Secrets Agent...")

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
# Delete old token
c.execute("DELETE FROM secrets_store WHERE name='google/gmail_token'")
# Insert new token
c.execute("INSERT INTO secrets_store (name, field, value) VALUES (?, ?, ?)",
          ('google/gmail_token', 'token_json', '{token_b64}'))
conn.commit()
conn.close()
print('OK')
PY"""
]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
if "OK" not in res.stdout:
    print(f"❌ Erro ao salvar token: {res.stderr}")
    sys.exit(1)

print("✅ Token salvo no Secrets Agent!")

# Verify
print("\n🔍 Verificando...")
cmd = [
    "ssh", f"homelab@{SECRETS_AGENT_HOST}",
    f"""python3 - <<'PY'
import sqlite3, base64, json
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='google/gmail_token'")
row = c.fetchone()
conn.close()

if row:
    data = json.loads(base64.b64decode(row[0]).decode())
    print(f"✅ Token verificado!")
    print(f"   Token: {{data['token'][:30]}}...")
    print(f"   Scopes: {{len(data.get('scopes', []))}} scopes")
PY"""
]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print(res.stdout.strip())

print("\n" + "="*70)
print("✅🎉 SUCESSO! Gmail API configurado!")
print("="*70)
print("\n📧 Agora você pode enviar emails!")
print("\nExecute:")
print("  python3 apply_real_job.py")
