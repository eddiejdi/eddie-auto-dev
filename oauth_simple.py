#!/usr/bin/env python3
"""Gerar URL OAuth simples."""
import json, subprocess, sys, base64
from urllib.parse import urlencode

# Get credentials
cmd = ["ssh", "homelab@192.168.15.2", """python3 - <<'PY'
import sqlite3, base64, json
conn = sqlite3.connect("/var/lib/eddie/secrets_agent/audit.db")
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
PY"""]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
try:
    creds_json = json.loads(res.stdout)
except:
    print("Erro ao obter credenciais")
    sys.exit(1)

client_id = creds_json["installed"]["client_id"]

# Generate auth URL
base_url = "https://accounts.google.com/o/oauth2/auth"
params = {
    'response_type': 'code',
    'client_id': client_id,
    'redirect_uri': 'http://localhost:8080/',
    'scope': 'https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/drive',
    'access_type': 'offline',
    'prompt': 'consent',
}

auth_url = f"{base_url}?{urlencode(params)}"

print("="*80)
print("🔗 COPIE E ABRA ESTA URL NO NAVEGADOR:")
print("="*80)
print(auth_url)
print("="*80)
print("\n📝 Após autorizar:")
print("   1. Copie o CÓDIGO da URL final (parte após code=)")
print("   2. Cole aqui")
print()

# Get code
code = "4/0ASc3gC16gYjihHF7ooLJ3R1XSRhwyilZhuo6Da0NuosXSYW6N9vpzGKQ5HoDzRa5OZNPCA"

# Exchange for token
import requests
token_url = "https://oauth2.googleapis.com/token"
client_secret = creds_json["installed"]["client_secret"]

data = {
    'code': code,
    'client_id': client_id,
    'client_secret': client_secret,
    'redirect_uri': 'http://localhost:8080/',
    'grant_type': 'authorization_code',
}

res = requests.post(token_url, data=data, timeout=30)

if res.status_code != 200:
    print(f"❌ Erro: {res.json()}")
    sys.exit(1)

token_resp = res.json()
print("✅ Token obtido!")

# Save to agent
token_json = json.dumps({
    'token': token_resp['access_token'],
    'refresh_token': token_resp.get('refresh_token'),
    'token_uri': 'https://oauth2.googleapis.com/token',
    'client_id': client_id,
    'client_secret': client_secret,
    'scopes': ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/drive'],
})

token_b64 = base64.b64encode(token_json.encode()).decode()

cmd = ["ssh", "homelab@192.168.15.2", f"""python3 - <<'PY'
import sqlite3, base64
conn = sqlite3.connect("/var/lib/eddie/secrets_agent/audit.db")
c = conn.cursor()
c.execute("DELETE FROM secrets_store WHERE name='google/gmail_token'")
c.execute("INSERT INTO secrets_store (name, field, value) VALUES (?, ?, ?)", ('google/gmail_token', 'token_json', '{token_b64}'))
conn.commit()
conn.close()
print('OK')
PY"""]

res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
if "OK" not in res.stdout:
    print(f"❌ Erro ao salvar: {res.stderr}")
    sys.exit(1)

print("✅ Token salvo!")
print("\n🎉 Pronto! Agora execute:")
print("   python3 apply_real_job.py")
