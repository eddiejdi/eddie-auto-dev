#!/usr/bin/env python3
"""
Setup Google APIs (Calendar + Gmail + Drive)
Configura autenticação OAuth2 para todas as APIs
"""

import os
import sys
import pickle
import shutil
from pathlib import Path
from typing import List

# Diretórios
BASE_DIR = Path(__file__).parent
CALENDAR_DIR = BASE_DIR / "calendar_data"
GMAIL_DIR = BASE_DIR / "gmail_data"
DRIVE_DIR = BASE_DIR / "drive_data"

# Escopos necessários para todos os serviços
COMBINED_SCOPES = [
    # Calendar
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    # Gmail
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    # Drive
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]


def find_credentials():
    """Procura arquivo de credenciais"""
    possible_paths = [
        BASE_DIR / "credentials.json",
        CALENDAR_DIR / "credentials.json",
        GMAIL_DIR / "credentials.json",
        DRIVE_DIR / "credentials.json",
        Path.home() / "credentials.json",
        Path.home() / "Downloads" / "credentials.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            print(f"✅ Credenciais encontradas: {path}")
            return path
    
    return None


def setup_directories():
    """Cria diretórios necessários"""
    CALENDAR_DIR.mkdir(exist_ok=True)
    GMAIL_DIR.mkdir(exist_ok=True)
    DRIVE_DIR.mkdir(exist_ok=True)
    print("✅ Diretórios criados")


def authenticate(scopes: List[str], credentials_path: Path):
    """Realiza autenticação OAuth2"""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("\n❌ Bibliotecas Google não instaladas!")
        print("Execute: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)
    
    creds = None
    token_path = CALENDAR_DIR / "token.pickle"
    
    # Verificar token existente
    if token_path.exists():
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)
    
    # Se não tiver credenciais ou estiverem inválidas
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 Renovando token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️ Falha ao renovar: {e}")
                creds = None
        
        if not creds:
            print("\n🔐 Iniciando fluxo de autenticação...")
            print("Uma janela do navegador será aberta.")
            print("Autorize o acesso e volte aqui.\n")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), 
                scopes
            )
            
            try:
                creds = flow.run_local_server(port=8080, open_browser=False)
            except Exception as e:
                print(f"⚠️  Erro ao iniciar servidor local: {e}")
                print("\nTentando com open_browser=False...")
                creds = flow.run_local_server(port=8080, open_browser=False)
    
    # Salvar token
    with open(token_path, 'wb') as f:
        pickle.dump(creds, f)
    
    # Copiar para Gmail e Drive também
    gmail_token = GMAIL_DIR / "token.pickle"
    drive_token = DRIVE_DIR / "token.pickle"
    shutil.copy(token_path, gmail_token)
    shutil.copy(token_path, drive_token)
    
    print("✅ Token salvo em todos os diretórios")
    
    return creds


def test_services(creds):
    """Testa os serviços"""
    from googleapiclient.discovery import build
    
    # Testar Calendar
    print("\n📅 Testando Google Calendar...")
    try:
        calendar = build('calendar', 'v3', credentials=creds)
        calendar_list = calendar.calendarList().list(maxResults=1).execute()
        print(f"   ✅ Calendar OK - {len(calendar_list.get('items', []))} calendário(s)")
    except Exception as e:
        print(f"   ❌ Calendar Error: {e}")
    
    # Testar Gmail
    print("\n📧 Testando Gmail...")
    try:
        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        print(f"   ✅ Gmail OK - Conta: {email}")
        
        # Contar mensagens
        result = gmail.users().messages().list(
            userId='me', 
            q='is:unread -in:spam -in:trash',
            maxResults=1
        ).execute()
        unread = result.get('resultSizeEstimate', 0)
        print(f"   📬 Emails não lidos: ~{unread}")
        
    except Exception as e:
        print(f"   ❌ Gmail Error: {e}")
    
    # Testar Drive
    print("\n📂 Testando Google Drive...")
    try:
        drive = build('drive', 'v3', credentials=creds)
        results = drive.files().list(pageSize=5, fields="files(id, name)").execute()
        files = results.get('files', [])
        print(f"   ✅ Drive OK - {len(files)} arquivo(s) recentes")
    except Exception as e:
        print(f"   ❌ Drive Error: {e}")


def main():
    print("="*60)
    print("🔐 SETUP GOOGLE APIs (Calendar + Gmail + Drive)")
    print("="*60)
    
    # 1. Criar diretórios
    print("\n📁 Configurando diretórios...")
    setup_directories()
    
    # 2. Encontrar credenciais
    print("\n🔍 Procurando credenciais...")
    creds_path = find_credentials()
    
    if not creds_path:
        print("""
❌ Arquivo credentials.json não encontrado!

Para configurar:
1. Acesse https://console.cloud.google.com/
2. Crie um projeto (ou use existente)
3. Ative as APIs:
   - Google Calendar API
   - Gmail API
   - Google Drive API
4. Vá em "Credenciais" > "Criar credenciais" > "ID do cliente OAuth"
5. Tipo: "Aplicativo para computador"
6. Baixe o arquivo JSON e renomeie para: credentials.json
7. Coloque em: /home/homelab/myClaude/credentials.json
8. Execute este script novamente
""")
        sys.exit(1)
    
    # Copiar credenciais para todos os diretórios
    shutil.copy(creds_path, CALENDAR_DIR / "credentials.json")
    shutil.copy(creds_path, GMAIL_DIR / "credentials.json")
    shutil.copy(creds_path, DRIVE_DIR / "credentials.json")
    print("✅ Credenciais copiadas")
    
    # 3. Autenticar
    print("\n🔐 Autenticando...")
    creds = authenticate(COMBINED_SCOPES, creds_path)
    
    # 4. Testar serviços
    test_services(creds)
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETO!")
    print("="*60)
    print("""
Agora você pode usar:

📅 Calendar:
   /calendar listar
   /calendar criar reunião amanhã às 14h

📧 Gmail:
   /gmail listar
   /gmail analisar
   /gmail limpar

📂 Drive:
   python google_drive_integration.py

Ou linguagem natural:
   "Quais são meus compromissos de amanhã?"
   "Quantos emails não lidos eu tenho?"
   "Buscar meu currículo no Drive"
""")


if __name__ == "__main__":
    main()
