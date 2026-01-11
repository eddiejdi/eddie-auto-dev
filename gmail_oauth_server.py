#!/usr/bin/env python3
"""
Gmail OAuth Server - Recebe callback do OAuth via tunnel fly.dev
"""

import os
import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Configurações
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events'
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials_web.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'gmail_data', 'token.json')
CALENDAR_TOKEN_FILE = os.path.join(BASE_DIR, 'calendar_data', 'token.json')

# Variável global para armazenar o código
auth_code = None
auth_state = None

class OAuthHandler(BaseHTTPRequestHandler):
    """Handler para receber o callback OAuth"""
    
    def log_message(self, format, *args):
        print(f"[OAuth] {args[0]}")
    
    def do_GET(self):
        global auth_code, auth_state
        
        parsed = urlparse(self.path)
        
        if parsed.path == '/oauth/google/callback':
            params = parse_qs(parsed.query)
            
            if 'code' in params:
                auth_code = params['code'][0]
                auth_state = params.get('state', [None])[0]
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Autenticação Concluída!</title>
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            display: flex; 
                            justify-content: center; 
                            align-items: center; 
                            height: 100vh; 
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }
                        .container {
                            background: white;
                            padding: 40px;
                            border-radius: 10px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                            text-align: center;
                        }
                        h1 { color: #28a745; }
                        p { color: #666; }
                        .icon { font-size: 64px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">✅</div>
                        <h1>Autenticação Concluída!</h1>
                        <p>O Gmail foi conectado com sucesso ao Eddie Assistant.</p>
                        <p>Você pode fechar esta janela.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
                
                # Sinaliza para parar o servidor
                threading.Thread(target=self.server.shutdown).start()
                
            elif 'error' in params:
                error = params['error'][0]
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Erro na Autenticação</title></head>
                <body>
                    <h1>❌ Erro na Autenticação</h1>
                    <p>Erro: {error}</p>
                    <p>Por favor, tente novamente.</p>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
        
        elif parsed.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        
        else:
            self.send_response(404)
            self.end_headers()


def authenticate_gmail():
    """Executa o fluxo de autenticação OAuth"""
    global auth_code
    
    print("=" * 60)
    print("🔐 GMAIL OAUTH AUTHENTICATION")
    print("=" * 60)
    
    # Criar diretórios se não existirem
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(CALENDAR_TOKEN_FILE), exist_ok=True)
    
    # Verificar se já existe token válido
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds and creds.valid:
                print("✅ Token existente ainda é válido!")
                return test_gmail_connection(creds)
        except Exception as e:
            print(f"⚠️  Token existente inválido: {e}")
    
    # Criar o flow OAuth
    print("\n📋 Iniciando fluxo OAuth...")
    
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri='https://homelab-tunnel-sparkling-sun-3565.fly.dev/oauth/google/callback'
    )
    
    # Gerar URL de autorização
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    print(f"\n🌐 Abrindo navegador para autenticação...")
    print(f"\n📎 URL: {auth_url[:80]}...")
    
    # Iniciar servidor local para receber o callback via tunnel
    print("\n⏳ Aguardando callback do OAuth...")
    print("   (O servidor está ouvindo na porta 8080)")
    print("   (O tunnel fly.dev vai redirecionar para cá)")
    
    # Abrir navegador
    webbrowser.open(auth_url)
    
    # Iniciar servidor
    server = HTTPServer(('0.0.0.0', 8080), OAuthHandler)
    server.timeout = 300  # 5 minutos timeout
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n❌ Autenticação cancelada pelo usuário")
        return False
    
    if not auth_code:
        print("\n❌ Não foi possível obter o código de autorização")
        return False
    
    print(f"\n✅ Código recebido! Trocando por token...")
    
    # Trocar código por token
    try:
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        
        # Salvar token
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"✅ Token salvo em: {TOKEN_FILE}")
        
        # Copiar para calendar também
        with open(CALENDAR_TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"✅ Token salvo em: {CALENDAR_TOKEN_FILE}")
        
        return test_gmail_connection(creds)
        
    except Exception as e:
        print(f"\n❌ Erro ao trocar código por token: {e}")
        return False


def test_gmail_connection(creds):
    """Testa a conexão com o Gmail"""
    print("\n" + "=" * 60)
    print("📧 TESTANDO CONEXÃO COM GMAIL")
    print("=" * 60)
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Obter perfil
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'N/A')
        total_msgs = profile.get('messagesTotal', 0)
        
        print(f"\n✅ Conectado com sucesso!")
        print(f"   📧 Email: {email}")
        print(f"   📬 Total de mensagens: {total_msgs:,}")
        
        # Listar últimos emails
        print(f"\n📋 Últimos 5 emails:")
        results = service.users().messages().list(
            userId='me', 
            maxResults=5,
            labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        for i, msg in enumerate(messages, 1):
            msg_detail = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject']
            ).execute()
            
            headers = {h['name']: h['value'] for h in msg_detail.get('payload', {}).get('headers', [])}
            subject = headers.get('Subject', '(Sem assunto)')[:50]
            sender = headers.get('From', '(Desconhecido)')[:30]
            
            print(f"   {i}. De: {sender}")
            print(f"      Assunto: {subject}")
        
        print("\n" + "=" * 60)
        print("🎉 GMAIL CONFIGURADO COM SUCESSO!")
        print("=" * 60)
        print("\nAgora você pode usar os comandos:")
        print("  /gmail listar      - Listar emails")
        print("  /gmail treinar     - Treinar IA com emails")
        print("  /gmail buscar X    - Buscar emails")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao testar conexão: {e}")
        return False


if __name__ == '__main__':
    authenticate_gmail()
