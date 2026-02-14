#!/usr/bin/env python3
"""Troca código OAuth por token e cria/obtém GOOGLE_AI_API_KEY."""
import json, urllib.parse, urllib.request, urllib.error, time, os, sys, subprocess

with open("credentials_google.json") as f:
    c = json.load(f)
    inst = c.get("installed", c.get("web", {}))

CLIENT_ID = inst["client_id"]
CLIENT_SECRET = inst["client_secret"]
PROJECT_ID = inst["project_id"]
REDIRECT_URI = "http://localhost:8085"

if len(sys.argv) < 2:
    print("Uso: python3 exchange_oauth_code.py <AUTH_CODE>")
    sys.exit(1)

AUTH_CODE = sys.argv[1]
print(f"Projeto: {PROJECT_ID}")

# 1. Trocar code por token
print("1/5 Trocando code por token...")
data = urllib.parse.urlencode({
    "code": AUTH_CODE,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read())
    access_token = token_data["access_token"]
    print(f"   OK token obtido")
except urllib.error.HTTPError as e:
    print(f"   ERRO {e.code}: {e.read().decode()[:300]}")
    sys.exit(1)


def api(method, url, body=None):
    d = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=d, method=method)
    r.add_header("Authorization", f"Bearer {access_token}")
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        print(f"   HTTP {e.code}: {b[:200]}")
        return {"error": True, "code": e.code, "body": b}


# 2. Habilitar API
print("2/5 Habilitando Generative Language API...")
r = api("POST", f"https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/generativelanguage.googleapis.com:enable", {})
if r and not r.get("error"):
    print("   OK habilitada")
elif r and r.get("code") == 409:
    print("   OK ja habilitada")

# 3. Verificar keys existentes
print("3/5 Verificando keys existentes...")
r = api("GET", f"https://apikeys.googleapis.com/v2/projects/{PROJECT_ID}/locations/global/keys")
api_key = None
if r and not r.get("error"):
    for k in r.get("keys", []):
        name = k.get("displayName", "sem-nome")
        kn = k.get("name", "")
        print(f"   Key encontrada: {name}")
        ks = api("GET", f"https://apikeys.googleapis.com/v2/{kn}/keyString")
        if ks and not ks.get("error"):
            api_key = ks.get("keyString")
            break

# 4. Criar se necessário
if not api_key:
    print("4/5 Criando nova API Key...")
    body = {
        "displayName": "Eddie Gemini API Key",
        "restrictions": {
            "apiTargets": [{"service": "generativelanguage.googleapis.com"}]
        },
    }
    r = api("POST", f"https://apikeys.googleapis.com/v2/projects/{PROJECT_ID}/locations/global/keys", body)
    if r and not r.get("error"):
        op = r.get("name", "")
        print(f"   Aguardando operacao...")
        for _ in range(30):
            time.sleep(2)
            op_r = api("GET", f"https://apikeys.googleapis.com/v2/{op}")
            if op_r and op_r.get("done"):
                kn = op_r.get("response", {}).get("name", "")
                ks = api("GET", f"https://apikeys.googleapis.com/v2/{kn}/keyString")
                if ks and not ks.get("error"):
                    api_key = ks.get("keyString")
                    print(f"   OK Key criada")
                break
            if op_r and op_r.get("error"):
                print(f"   Erro: {op_r}")
                break
else:
    print("4/5 Usando key existente")

if not api_key:
    print("\nFALHA. Acesse manualmente: https://aistudio.google.com/apikey")
    sys.exit(1)

# 5. Salvar
print(f"5/5 Key obtida: {api_key[:10]}...{api_key[-4:]}")

# .env local
lines = []
if os.path.exists(".env"):
    with open(".env") as f:
        lines = [l for l in f.readlines() if not l.startswith("GOOGLE_AI_API_KEY=")]
lines.append(f"GOOGLE_AI_API_KEY={api_key}\n")
with open(".env", "w") as f:
    f.writelines(lines)
print("   Salvo em .env")

# Secrets Agent via SSH
try:
    payload = json.dumps({
        "name": "eddie-google-ai-api-key",
        "value": api_key,
        "metadata": {"service": "gemini", "created_by": "exchange_oauth_code.py"}
    })
    cmd = [
        "ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
        f"curl -sf -X POST http://localhost:8088/secrets -H 'Content-Type: application/json' -H 'X-API-Key: eddie-secrets-2026' -d '{payload}'"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        print("   Salvo no Secrets Agent")
    else:
        print(f"   Secrets Agent: {r.stderr[:100]}")
except Exception as e:
    print(f"   Secrets Agent offline: {e}")

print(f"\nexport GOOGLE_AI_API_KEY={api_key}")
print("Done!")
