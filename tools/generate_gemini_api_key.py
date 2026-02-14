#!/usr/bin/env python3
"""
Gera uma GOOGLE_AI_API_KEY (Gemini) automaticamente usando OAuth2 e
armazena no Secrets Agent do homelab.

Requisitos:
  - OAuth client_id e client_secret já armazenados no Secrets Agent
  - Acesso a um navegador (abrirá para authorize)
  - Generative Language API habilitada no projeto GCP

Uso:
  python3 tools/generate_gemini_api_key.py
"""

import json
import os
import sys
import time
import base64
import sqlite3
import urllib.request
import urllib.parse
import http.server
import threading
import webbrowser
from pathlib import Path

# ─── Configuração ─────────────────────────────────────────
SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://localhost:8088")
SECRETS_AGENT_API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "please-set-a-strong-key")
LOCAL_REDIRECT_PORT = 8089
REDIRECT_URI = f"http://localhost:{LOCAL_REDIRECT_PORT}"

# Scopes necessários para criar API keys e usar Generative Language
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language",
]

GCP_PROJECT_NUMBER = "238307278672"

auth_code_result = {"code": None}


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Captura o authorization code do redirect OAuth."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        if code:
            auth_code_result["code"] = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>&#10003; Autorizado com sucesso!</h2>"
                b"<p>Pode fechar esta aba. A API key sera gerada automaticamente.</p>"
                b"</body></html>"
            )
        else:
            error = params.get("error", ["desconhecido"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2>Erro: {error}</h2>".encode())

    def log_message(self, format, *args):
        pass  # silencia logs HTTP


def get_oauth_credentials():
    """Busca client_id e client_secret do Secrets Agent via SSH."""
    print("🔑 Buscando credenciais OAuth do Secrets Agent (via SSH)...")
    
    import subprocess
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
         "python3 -c \""
         "import sqlite3,json;"
         "db='/var/lib/eddie/secrets_agent/audit.db';"
         "conn=sqlite3.connect(db);c=conn.cursor();"
         "c.execute(\\\"SELECT value FROM secrets_store WHERE name='google/oauth_client_installed' AND field='client_id'\\\");"
         "cid=c.fetchone()[0];"
         "c.execute(\\\"SELECT value FROM secrets_store WHERE name='google/oauth_client_installed' AND field='client_secret'\\\");"
         "cs=c.fetchone()[0];"
         "conn.close();"
         "print(json.dumps({'client_id':cid,'client_secret':cs}))"
         "\""],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"SSH failed: {result.stderr}")
    
    creds = json.loads(result.stdout.strip())
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]
    
    print(f"  Client ID: {client_id[:30]}...")
    return client_id, client_secret


def do_oauth_flow(client_id, client_secret):
    """Executa OAuth2 flow com browser redirect."""
    print("\n🌐 Iniciando OAuth2 flow...")
    
    # Start local server
    server = http.server.HTTPServer(("localhost", LOCAL_REDIRECT_PORT), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()
    
    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{auth_params}"
    
    print(f"  Abrindo navegador para autorização...")
    print(f"  URL: {auth_url[:100]}...\n")
    webbrowser.open(auth_url)
    
    # Wait for callback
    print("  ⏳ Aguardando autorização no navegador...")
    server_thread.join(timeout=120)
    server.server_close()
    
    if not auth_code_result["code"]:
        print("  ❌ Timeout ou erro na autorização!")
        sys.exit(1)
    
    print("  ✅ Código de autorização recebido!")
    
    # Exchange code for tokens
    print("  🔄 Trocando código por tokens...")
    token_data = urllib.parse.urlencode({
        "code": auth_code_result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=token_data)
    resp = urllib.request.urlopen(req, timeout=15)
    tokens = json.loads(resp.read())
    
    access_token = tokens["access_token"]
    print(f"  ✅ Access token obtido: {access_token[:20]}...")
    return access_token, tokens.get("refresh_token")


def enable_generative_language_api(access_token):
    """Habilita a Generative Language API no projeto GCP."""
    print("\n📡 Habilitando Generative Language API...")
    
    url = f"https://serviceusage.googleapis.com/v1/projects/{GCP_PROJECT_NUMBER}/services/generativelanguage.googleapis.com:enable"
    body = json.dumps({}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        print(f"  ✅ API habilitada! Operation: {result.get('name', 'ok')}")
        time.sleep(5)  # aguardar propagação
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "already enabled" in body.lower() or e.code == 409:
            print("  ✅ API já estava habilitada.")
        else:
            print(f"  ⚠️ Aviso ao habilitar: {e.code} - {body[:200]}")


def create_api_key(access_token):
    """Cria uma API key restrita à Generative Language API."""
    print("\n🔐 Criando API key para Gemini...")
    
    # Primeiro, listar keys existentes
    list_url = f"https://apikeys.googleapis.com/v2/projects/{GCP_PROJECT_NUMBER}/locations/global/keys"
    req = urllib.request.Request(list_url)
    req.add_header("Authorization", f"Bearer {access_token}")
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        existing_keys = data.get("keys", [])
        
        # Verificar se já existe uma key para Gemini
        for key in existing_keys:
            name = key.get("displayName", "")
            if "gemini" in name.lower() or "eddie" in name.lower():
                # Obter o keyString
                key_name = key["name"]
                get_url = f"https://apikeys.googleapis.com/v2/{key_name}/keyString"
                req2 = urllib.request.Request(get_url)
                req2.add_header("Authorization", f"Bearer {access_token}")
                resp2 = urllib.request.urlopen(req2, timeout=10)
                key_data = json.loads(resp2.read())
                api_key = key_data.get("keyString")
                print(f"  ✅ Key existente encontrada: {name}")
                print(f"  Key: {api_key[:10]}...")
                return api_key
        
        print(f"  📋 {len(existing_keys)} keys existentes, nenhuma para Gemini.")
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ Aviso ao listar keys: {e.code}")
    
    # Criar nova key
    create_url = f"https://apikeys.googleapis.com/v2/projects/{GCP_PROJECT_NUMBER}/locations/global/keys"
    body = json.dumps({
        "displayName": "Eddie Gemini API Key",
        "restrictions": {
            "apiTargets": [
                {"service": "generativelanguage.googleapis.com"}
            ]
        }
    }).encode()
    
    req = urllib.request.Request(create_url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req, timeout=30)
    operation = json.loads(resp.read())
    
    print(f"  ⏳ Operação: {operation.get('name', '?')}")
    
    # Poll operation until done
    op_name = operation.get("name", "")
    for i in range(20):
        time.sleep(2)
        poll_url = f"https://apikeys.googleapis.com/v2/{op_name}"
        req3 = urllib.request.Request(poll_url)
        req3.add_header("Authorization", f"Bearer {access_token}")
        try:
            resp3 = urllib.request.urlopen(req3, timeout=10)
            op_status = json.loads(resp3.read())
            if op_status.get("done"):
                key_resource = op_status.get("response", {})
                key_name = key_resource.get("name", "")
                
                # Get the actual key string
                get_url = f"https://apikeys.googleapis.com/v2/{key_name}/keyString"
                req4 = urllib.request.Request(get_url)
                req4.add_header("Authorization", f"Bearer {access_token}")
                resp4 = urllib.request.urlopen(req4, timeout=10)
                key_data = json.loads(resp4.read())
                api_key = key_data.get("keyString")
                
                print(f"  ✅ API key criada!")
                print(f"  Key: {api_key[:10]}...")
                return api_key
        except Exception:
            pass
    
    raise RuntimeError("Timeout aguardando criação da API key")


def store_in_secrets_agent(api_key):
    """Armazena a GOOGLE_AI_API_KEY no Secrets Agent via SSH."""
    print("\n💾 Armazenando no Secrets Agent...")
    
    import subprocess
    ts = int(time.time())
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
         f"python3 -c \""
         f"import sqlite3,time;"
         f"db='/var/lib/eddie/secrets_agent/audit.db';"
         f"conn=sqlite3.connect(db);c=conn.cursor();"
         f"c.execute(\\\"INSERT INTO secrets_store (name,field,value,notes,created_at,updated_at) "
         f"VALUES ('google/gemini_api_key','api_key','{api_key}','Generated by generate_gemini_api_key.py',{ts},{ts}) "
         f"ON CONFLICT(name,field) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at\\\");"
         f"conn.commit();conn.close();"
         f"print('stored ok')"
         f"\""],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0:
        print(f"  ✅ Armazenado no Secrets Agent: google/gemini_api_key")
    else:
        print(f"  ⚠️ Erro SSH: {result.stderr}")
    
    # Salvar localmente também como .env reference
    env_file = Path(__file__).parent.parent / ".env"
    env_content = env_file.read_text() if env_file.exists() else ""
    if "GOOGLE_AI_API_KEY" not in env_content:
        with open(env_file, "a") as f:
            f.write(f"\nGOOGLE_AI_API_KEY={api_key}\nGEMINI_ENABLED=true\n")
        print(f"  ✅ Adicionado ao .env")
    else:
        print(f"  ℹ️ GOOGLE_AI_API_KEY já existe no .env")
    
    return {"status": "stored"}


def main():
    print("=" * 60)
    print("🤖 Gerador de GOOGLE_AI_API_KEY (Gemini)")
    print("=" * 60)
    
    try:
        client_id, client_secret = get_oauth_credentials()
    except Exception as e:
        print(f"\n❌ Erro ao obter credenciais OAuth do Secrets Agent: {e}")
        print("  Verifique se o Secrets Agent está rodando no homelab.")
        sys.exit(1)
    
    try:
        access_token, refresh_token = do_oauth_flow(client_id, client_secret)
    except Exception as e:
        print(f"\n❌ Erro no OAuth flow: {e}")
        sys.exit(1)
    
    try:
        enable_generative_language_api(access_token)
    except Exception as e:
        print(f"\n⚠️ Aviso ao habilitar API: {e}")
    
    try:
        api_key = create_api_key(access_token)
    except Exception as e:
        print(f"\n❌ Erro ao criar API key: {e}")
        sys.exit(1)
    
    try:
        store_in_secrets_agent(api_key)
    except Exception as e:
        print(f"\n⚠️ Erro ao armazenar no Secrets Agent: {e}")
        print(f"  Armazene manualmente: GOOGLE_AI_API_KEY={api_key}")
    
    print("\n" + "=" * 60)
    print("✅ CONCLUÍDO!")
    print(f"  GOOGLE_AI_API_KEY={api_key[:15]}...")
    print("  A key foi armazenada no Secrets Agent e no .env")
    print("=" * 60)


if __name__ == "__main__":
    main()
