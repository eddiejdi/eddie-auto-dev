#!/usr/bin/env python3
"""Trocar código de autorização por token OAuth."""
import json
import subprocess
import sys
import base64
from urllib.parse import parse_qs, urlparse

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_DB = "/var/lib/eddie/secrets_agent/audit.db"

# Código fornecido pelo usuário
auth_code = "4/0ASc3gC2hi5hevY1Ddazlw9qpaQnEfzorFGrqlfdiuxcyxQlodu8UMnC9QC3HP5zesRLLKQ"

print("="*70)
print("🔄 TROCANDO CÓDIGO POR TOKEN GMAIL")
print("="*70 + "\n")

print(f"📥 Obtendo credenciais do Secrets Agent...")

# Get credentials from agent
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
except Exception as e:
    print(f"❌ Erro ao parsear credenciais: {e}")
    sys.exit(1)

client_id = creds_json["installed"]["client_id"]
client_secret = creds_json["installed"]["client_secret"]

print(f"✅ Credenciais obtidas")
print(f"   Project: {client_id[:30]}...")

# Exchange code for token
print(f"\n🔄 Trocando código por access token...")

import requests

token_url = "https://oauth2.googleapis.com/token"
data = {
    'code': auth_code,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': 'http://localhost:8080/',  # com trailing slash
    'grant_type': 'authorization_code',
}

try:
    res = requests.post(token_url, data=data, timeout=30)
    if res.status_code != 200:
        print(f"❌ Erro ao obter token: {res.text}")
        sys.exit(1)
    
    token_resp = res.json()
except Exception as e:
    print(f"❌ Erro na requisição: {e}")
    sys.exit(1)

print("✅ Token obtido com sucesso!")
print(f"   access_token: {token_resp['access_token'][:40]}...")
print(f"   refresh_token: {token_resp.get('refresh_token', 'N/A')[:40] if token_resp.get('refresh_token') else 'N/A'}...")
print(f"   expires_in: {token_resp.get('expires_in')} segundos")

# Save to Secrets Agent
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
    print(f"❌ Erro ao salvar: {res.stderr}")
    sys.exit(1)

print("✅ Token salvo no Secrets Agent!")

# Verify
print("\n🔍 Verificando token salvo...")
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
    try:
        data = json.loads(base64.b64decode(row[0]).decode())
        print(f"✅ Token verificado!")
        print(f"   Escopos: {data.get('scopes')}")
        print(f"   Token: {data.get('token')[:30]}...")
        return 0
    except Exception as e:
        print(f"❌ Erro ao decodificar: {{e}}")
        return 1
else:
    print("❌ Token não encontrado")
    return 1
PY"""
]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print(res.stdout)

print("\n" + "="*70)
print("✅ SUCESSO! GMAIL API CONFIGURADO!")
print("="*70)
print("\n🎉 Agora você pode enviar emails!")
print("\nExecute um destes comandos:")
print("  • python3 send_via_curl.py")
print("  • python3 apply_real_job.py")
print("  • python3 send_email_draft.py")
