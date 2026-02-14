#!/usr/bin/env python3
"""
Obtém uma GOOGLE_AI_API_KEY via Google Cloud REST API.
Fluxo: OAuth (scope cloud-platform) → habilita Generative Language API → cria API Key → salva.
"""
import json
import http.server
import threading
import urllib.parse
import webbrowser
import time
import sys
import os

# --- Credenciais do projeto ---
with open("credentials_google.json") as f:
    _creds = json.load(f)
    _inst = _creds.get("installed", _creds.get("web", {}))

CLIENT_ID = _inst["client_id"]
CLIENT_SECRET = _inst["client_secret"]
PROJECT_ID = _inst["project_id"]  # homelab-483803

REDIRECT_URI = "http://localhost:8085"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"

import urllib.request
import urllib.error

auth_code = None

class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in qs:
            auth_code = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>OK! Autorizacao recebida. Pode fechar esta aba.</h1>")
        else:
            err = qs.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Erro: {err}</h1>".encode())
    def log_message(self, *a):
        pass


def get_access_token():
    """OAuth flow para obter access_token com scope cloud-platform."""
    global auth_code
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&response_type=code&scope={urllib.parse.quote(SCOPE)}"
        f"&access_type=offline&prompt=consent"
    )
    
    server = http.server.HTTPServer(("localhost", 8085), OAuthHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    
    print(f"\n🌐 Abrindo navegador para autorização...")
    print(f"   Se não abrir automaticamente, acesse:\n   {auth_url}\n")
    webbrowser.open(auth_url)
    
    # Aguardar callback
    for _ in range(120):
        if auth_code:
            break
        time.sleep(1)
    
    server.server_close()
    
    if not auth_code:
        print("❌ Timeout aguardando autorização.")
        sys.exit(1)
    
    print("✅ Código de autorização recebido!")
    
    # Trocar code por token
    data = urllib.parse.urlencode({
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read())
    
    return token_data["access_token"]


def api_call(method, url, token, body=None):
    """Helper para chamadas REST."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"   ⚠️  HTTP {e.code}: {err_body[:200]}")
        return {"error": True, "code": e.code, "body": err_body}


def enable_api(token):
    """Habilita a Generative Language API no projeto."""
    print("\n🔧 Habilitando Generative Language API...")
    url = f"https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/generativelanguage.googleapis.com:enable"
    result = api_call("POST", url, token, {})
    if result and not result.get("error"):
        print("   ✅ API habilitada (ou já estava habilitada).")
        return True
    elif result.get("code") == 409:
        print("   ✅ API já estava habilitada.")
        return True
    else:
        print(f"   ❌ Falha ao habilitar API.")
        return False


def list_existing_keys(token):
    """Lista API keys existentes no projeto."""
    print("\n🔍 Verificando API keys existentes...")
    url = f"https://apikeys.googleapis.com/v2/projects/{PROJECT_ID}/locations/global/keys"
    result = api_call("GET", url, token)
    if result and not result.get("error"):
        keys = result.get("keys", [])
        for k in keys:
            name = k.get("displayName", "sem-nome")
            uid = k.get("uid", "?")
            print(f"   📌 {name} (uid: {uid})")
            # Buscar valor da key
            key_name = k.get("name", "")
            key_detail = api_call("GET", f"https://apikeys.googleapis.com/v2/{key_name}/keyString", token)
            if key_detail and not key_detail.get("error"):
                return key_detail.get("keyString")
        return None
    return None


def create_api_key(token):
    """Cria uma nova API key para a Generative Language API."""
    print("\n🔑 Criando API Key para Gemini...")
    url = f"https://apikeys.googleapis.com/v2/projects/{PROJECT_ID}/locations/global/keys"
    body = {
        "displayName": "Eddie Gemini API Key",
        "restrictions": {
            "apiTargets": [
                {"service": "generativelanguage.googleapis.com"}
            ]
        }
    }
    result = api_call("POST", url, token, body)
    if result and not result.get("error"):
        # A criação retorna uma operação — precisamos aguardar
        op_name = result.get("name", "")
        print(f"   ⏳ Operação: {op_name}")
        # Aguardar operação concluir
        for i in range(30):
            time.sleep(2)
            op_result = api_call("GET", f"https://apikeys.googleapis.com/v2/{op_name}", token)
            if op_result and op_result.get("done"):
                key_name = op_result.get("response", {}).get("name", "")
                print(f"   ✅ Key criada: {key_name}")
                # Obter o valor da key
                key_str = api_call("GET", f"https://apikeys.googleapis.com/v2/{key_name}/keyString", token)
                if key_str and not key_str.get("error"):
                    return key_str.get("keyString")
                break
            if op_result and op_result.get("error"):
                print(f"   ❌ Erro na operação: {op_result}")
                break
        return None
    else:
        print(f"   ❌ Falha ao criar key.")
        return None


def store_in_secrets_agent(api_key):
    """Armazena no Secrets Agent via SSH no homelab."""
    print("\n💾 Armazenando no Secrets Agent...")
    
    # Tentar via SSH no homelab
    import subprocess
    cmd = [
        "ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
        f"""curl -s -X POST http://localhost:8088/secrets \
            -H 'Content-Type: application/json' \
            -H 'X-API-Key: eddie-secrets-2026' \
            -d '{{"name":"eddie-google-ai-api-key","value":"{api_key}","metadata":{{"service":"gemini","created_by":"get_gemini_api_key.py"}}}}'"""
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and "error" not in r.stdout.lower():
            print(f"   ✅ Armazenado no Secrets Agent: eddie-google-ai-api-key")
            return True
        else:
            print(f"   ⚠️  Resposta: {r.stdout[:200]}")
    except Exception as e:
        print(f"   ⚠️  SSH falhou: {e}")
    
    return False


def save_locally(api_key):
    """Salva a key em .env e exporta."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_file):
        with open(env_file) as f:
            lines = [l for l in f.readlines() if not l.startswith("GOOGLE_AI_API_KEY=")]
    
    lines.append(f"GOOGLE_AI_API_KEY={api_key}\n")
    
    with open(env_file, "w") as f:
        f.writelines(lines)
    print(f"   ✅ Salvo em .env")


def main():
    print("=" * 60)
    print("🔑 Obter GOOGLE_AI_API_KEY (Gemini)")
    print("=" * 60)
    print(f"   Projeto: {PROJECT_ID}")
    
    # 1. OAuth
    token = get_access_token()
    
    # 2. Habilitar API
    enable_api(token)
    
    # 3. Verificar keys existentes
    existing = list_existing_keys(token)
    if existing:
        api_key = existing
        print(f"\n✅ API Key existente encontrada!")
    else:
        # 4. Criar nova key
        api_key = create_api_key(token)
    
    if not api_key:
        print("\n❌ Não foi possível obter a API Key.")
        print("   Acesse manualmente: https://aistudio.google.com/apikey")
        sys.exit(1)
    
    print(f"\n🎉 GOOGLE_AI_API_KEY obtida com sucesso!")
    print(f"   Key: {api_key[:10]}...{api_key[-4:]}")
    
    # 5. Salvar
    save_locally(api_key)
    store_in_secrets_agent(api_key)
    
    # 6. Exportar
    print(f"\n📋 Para usar agora:")
    print(f"   export GOOGLE_AI_API_KEY={api_key}")
    print(f"\n✅ Gemini pronto para uso!")


if __name__ == "__main__":
    main()
