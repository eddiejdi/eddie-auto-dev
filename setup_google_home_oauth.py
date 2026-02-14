#!/usr/bin/env python3
"""
Script de configuração OAuth 2.0 para Google Home / Smart Device Management API

Este script guia o processo de autenticação OAuth e salva os tokens necessários.

Pré-requisitos:
1. Projeto no Google Cloud Console criado
2. Smart Device Management API habilitada
3. OAuth 2.0 Client ID criado (tipo Web Application)
4. Redirect URI configurado: http://localhost:8080
5. Device Access Project criado em https://console.nest.google.com/device-access/
"""

import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import sys
from pathlib import Path

# Configurações OAuth: carregam de `credentials_google.json` ou variáveis de ambiente
import os

REDIRECT_URI = "http://localhost:8080"

# Valores padrão (podem ser sobrescritos por credentials_google.json ou env)
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
SDM_PROJECT_ID = os.getenv("GOOGLE_SDM_PROJECT_ID", "")

# Escopos e endpoints
SCOPES = ["https://www.googleapis.com/auth/sdm.service"]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Tentar carregar arquivo `credentials_google.json` quando presente
try:
    with open("credentials_google.json") as f:
        cj = json.load(f)
        inst = cj.get("installed", cj.get("web", {}))
        if not OAUTH_CLIENT_ID:
            OAUTH_CLIENT_ID = inst.get("client_id", "")
        if not OAUTH_CLIENT_SECRET:
            OAUTH_CLIENT_SECRET = inst.get("client_secret", "")
        if not SDM_PROJECT_ID:
            SDM_PROJECT_ID = inst.get("project_id", SDM_PROJECT_ID)
except FileNotFoundError:
    pass

# Armazenamento de código de autorização
authorization_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    """Handler HTTP para receber callback OAuth"""
    
    def do_GET(self):
        global authorization_code
        
        # Parse query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            authorization_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body>
                <h1>Autorizacao concluida!</h1>
                <p>Voce pode fechar esta janela e voltar ao terminal.</p>
                <script>window.close();</script>
            </body>
            </html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Erro na autorizacao</h1></body></html>")
    
    def log_message(self, format, *args):
        # Suprimir logs do servidor HTTP
        pass


def get_authorization_code():
    """Abre navegador para autorização e captura código"""
    global authorization_code
    
    # Construir URL de autorização
    auth_params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # Para obter refresh_token
        "prompt": "consent",
    }
    
    auth_url_full = AUTH_URL + "?" + "&".join(
        f"{k}={requests.utils.quote(str(v))}" for k, v in auth_params.items()
    )
    
    print("\n" + "="*60)
    print("PASSO 1: Autorização OAuth")
    print("="*60)
    print("\nAbrindo navegador para autorização...")
    print(f"\nSe o navegador não abrir, acesse manualmente:")
    print(f"{auth_url_full}\n")
    
    # Abrir navegador
    webbrowser.open(auth_url_full)
    
    # Iniciar servidor HTTP local para receber callback
    print("Aguardando callback em http://localhost:8080...")
    server = HTTPServer(('localhost', 8080), OAuthHandler)
    
    # Processar apenas uma requisição (o callback)
    server.handle_request()
    
    if authorization_code:
        print("\n✓ Código de autorização recebido!")
        return authorization_code
    else:
        print("\n❌ Erro: Não foi possível obter código de autorização")
        return None


def exchange_code_for_tokens(code):
    """Troca código de autorização por access_token e refresh_token"""
    print("\n" + "="*60)
    print("PASSO 2: Obtendo tokens de acesso")
    print("="*60)
    
    token_data = {
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    
    response = requests.post(TOKEN_URL, data=token_data)
    result = response.json()
    
    if 'access_token' in result:
        print("\n✓ Tokens obtidos com sucesso!")
        return result
    else:
        print(f"\n❌ Erro ao obter tokens: {result}")
        return None


def save_credentials(tokens):
    """Salva credenciais em arquivo JSON"""
    credentials = {
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "token_type": tokens["token_type"],
        "expires_in": tokens["expires_in"],
        "sdm_project_id": SDM_PROJECT_ID,
    }
    
    # Salvar em arquivo
    cred_file = Path("google_home_credentials.json")
    with open(cred_file, 'w') as f:
        json.dump(credentials, f, indent=2)
    
    print(f"\n✓ Credenciais salvas em: {cred_file.absolute()}")
    
    # Também salvar no diretório de dados dos agentes
    try:
        from specialized_agents.config import DATA_DIR
        agent_cred_file = DATA_DIR / "home_automation" / "google_credentials.json"
        agent_cred_file.parent.mkdir(parents=True, exist_ok=True)
        with open(agent_cred_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        print(f"✓ Credenciais também salvas em: {agent_cred_file}")
    except:
        pass
    
    return credentials


def test_api_access(access_token):
    """Testa acesso à API com o token obtido"""
    print("\n" + "="*60)
    print("PASSO 3: Testando acesso à API")
    print("="*60)
    
    url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{SDM_PROJECT_ID}/devices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        devices = result.get("devices", [])
        print(f"\n✓ API funcionando! Encontrados {len(devices)} dispositivos:")
        for dev in devices:
            name = dev.get("name", "Unknown")
            dev_type = dev.get("type", "Unknown")
            traits = list(dev.get("traits", {}).keys())
            print(f"  - {name}")
            print(f"    Tipo: {dev_type}")
            print(f"    Traits: {', '.join(traits[:3])}...")
        return True
    else:
        print(f"\n❌ Erro ao acessar API: {response.status_code}")
        print(response.text)
        return False


def main():
    print("="*60)
    print("CONFIGURAÇÃO GOOGLE HOME / SMART DEVICE MANAGEMENT")
    print("="*60)
    
    # Verificar se credenciais estão preenchidas
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET or not SDM_PROJECT_ID:
        print("\n❌ ERRO: Credenciais não configuradas!")
        print("\nEdite este script e preencha:")
        print("  - OAUTH_CLIENT_ID")
        print("  - OAUTH_CLIENT_SECRET")
        print("  - SDM_PROJECT_ID")
        print("\nPara obter essas credenciais, siga o guia em:")
        print("  ./GOOGLE_HOME_SETUP_GUIDE.md")
        return 1
    
    try:
        # Passo 1: Obter código de autorização
        code = get_authorization_code()
        if not code:
            return 1
        
        # Passo 2: Trocar código por tokens
        tokens = exchange_code_for_tokens(code)
        if not tokens:
            return 1
        
        # Passo 3: Salvar credenciais
        credentials = save_credentials(tokens)
        
        # Passo 4: Testar API
        test_api_access(credentials["access_token"])
        
        print("\n" + "="*60)
        print("✓ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print("\nVariáveis de ambiente para usar no sistema:")
        print(f"export GOOGLE_HOME_TOKEN='{credentials['access_token']}'")
        print(f"export GOOGLE_SDM_PROJECT_ID='{SDM_PROJECT_ID}'")
        print("\nOu adicione ao .env:")
        print("GOOGLE_HOME_TOKEN='{}'".format(credentials['access_token']))
        print("GOOGLE_SDM_PROJECT_ID='{}'".format(SDM_PROJECT_ID))
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário")
        return 1
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
