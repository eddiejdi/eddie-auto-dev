#!/usr/bin/env python3
"""
Setup Visual do Gmail OAuth
Guia passo-a-passo para configurar autenticação
"""

import os
import sys
import json
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent
GMAIL_DIR = BASE_DIR / "gmail_data"
CALENDAR_DIR = BASE_DIR / "calendar_data"
CREDS_FILE = BASE_DIR / "credentials.json"

def print_banner():
    print("""
╔════════════════════════════════════════════════════════════════╗
║      🔐 SETUP GMAIL OAUTH - Shared Assistant                    ║
║      Configuração de autenticação Google                        ║
╚════════════════════════════════════════════════════════════════╝
""")

def check_existing_creds():
    """Verifica credenciais existentes"""
    locations = [
        CREDS_FILE,
        GMAIL_DIR / "credentials.json",
        CALENDAR_DIR / "credentials.json",
        Path.home() / "Downloads" / "credentials.json",
        Path.home() / "credentials.json"
    ]
    
    for loc in locations:
        if loc.exists():
            print(f"✅ Credenciais encontradas: {loc}")
            return loc
    
    return None

def setup_step_by_step():
    """Guia passo-a-passo"""
    
    print("""
📋 PASSO A PASSO:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 1: Google Cloud Console
   
   Vou abrir o Google Cloud Console no seu navegador.
   
   Se você NÃO tem um projeto:
   1. Clique em "Criar Projeto"
   2. Nome: "Shared Assistant"
   3. Clique em "Criar"

   Se você JÁ tem um projeto:
   1. Selecione o projeto existente no menu superior
""")
    input("   Pressione ENTER para abrir o Console... ")
    webbrowser.open("https://console.cloud.google.com/")
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 2: Ativar Gmail API
   
   Vou abrir a página da Gmail API.
   
   1. Clique em "ATIVAR" (ou "ENABLE")
   2. Aguarde a API ser ativada
""")
    input("   Pressione ENTER para abrir Gmail API... ")
    webbrowser.open("https://console.cloud.google.com/apis/library/gmail.googleapis.com")
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 3: Ativar Calendar API (se não ativou ainda)
   
   1. Clique em "ATIVAR"
""")
    input("   Pressione ENTER para abrir Calendar API... ")
    webbrowser.open("https://console.cloud.google.com/apis/library/calendar-json.googleapis.com")
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 4: Configurar Tela de Consentimento OAuth
   
   1. Vá em "Tela de consentimento OAuth"
   2. Tipo de usuário: "Externo"
   3. Clique em "CRIAR"
   4. Preencha:
      - Nome do app: Shared Assistant
      - Email de suporte: seu email
      - Email do desenvolvedor: seu email
   5. Clique em "SALVAR E CONTINUAR"
   6. Em "Escopos", clique em "ADICIONAR OU REMOVER ESCOPOS"
      - Adicione: Gmail API (todos os escopos)
      - Adicione: Google Calendar API (todos os escopos)
   7. Clique em "SALVAR E CONTINUAR"
   8. Em "Usuários de teste", adicione seu email
   9. Clique em "SALVAR E CONTINUAR"
""")
    input("   Pressione ENTER para abrir Tela de Consentimento... ")
    webbrowser.open("https://console.cloud.google.com/apis/credentials/consent")
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 5: Criar Credenciais OAuth
   
   1. Vá em "Credenciais"
   2. Clique em "+ CRIAR CREDENCIAIS"
   3. Selecione "ID do cliente OAuth"
   4. Tipo de aplicativo: "Aplicativo para computador"
   5. Nome: "Shared Assistant Desktop"
   6. Clique em "CRIAR"
   7. Clique em "FAZER DOWNLOAD DO JSON"
   8. Renomeie o arquivo para: credentials.json
   9. Mova para: /home/homelab/myClaude/credentials.json
""")
    input("   Pressione ENTER para abrir página de Credenciais... ")
    webbrowser.open("https://console.cloud.google.com/apis/credentials")
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 PASSO 6: Verificar Download

   O arquivo baixado terá um nome como:
   client_secret_XXXXX.apps.googleusercontent.com.json
   
   Renomeie para: credentials.json
   E mova para: /home/homelab/myClaude/
""")
    
    input("   Pressione ENTER quando o arquivo estiver pronto... ")

def find_downloaded_creds():
    """Procura credenciais baixadas"""
    downloads = Path.home() / "Downloads"
    
    # Procurar por padrões comuns
    patterns = [
        "credentials.json",
        "client_secret*.json",
        "*oauth*.json"
    ]
    
    for pattern in patterns:
        files = list(downloads.glob(pattern))
        if files:
            # Pegar o mais recente
            latest = max(files, key=lambda f: f.stat().st_mtime)
            return latest
    
    return None

def copy_credentials():
    """Copia credenciais para os diretórios corretos"""
    import shutil
    
    # Procurar credenciais
    creds = check_existing_creds()
    
    if not creds:
        # Tentar encontrar em Downloads
        creds = find_downloaded_creds()
        
        if creds:
            print(f"📂 Encontrado em Downloads: {creds.name}")
        else:
            print("""
❌ Credenciais não encontradas!

Por favor, coloque o arquivo credentials.json em:
/home/homelab/myClaude/credentials.json

Ou em Downloads como:
client_secret_*.json
""")
            return False
    
    # Criar diretórios
    GMAIL_DIR.mkdir(exist_ok=True)
    CALENDAR_DIR.mkdir(exist_ok=True)
    
    # Copiar para os locais corretos
    import shutil
    
    if creds != CREDS_FILE:
        shutil.copy(creds, CREDS_FILE)
        print(f"✅ Copiado para: {CREDS_FILE}")
    
    shutil.copy(creds, GMAIL_DIR / "credentials.json")
    print(f"✅ Copiado para: {GMAIL_DIR / 'credentials.json'}")
    
    shutil.copy(creds, CALENDAR_DIR / "credentials.json")
    print(f"✅ Copiado para: {CALENDAR_DIR / 'credentials.json'}")
    
    return True

def authenticate():
    """Realiza autenticação OAuth"""
    print("\n🔐 Iniciando autenticação...")
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
        
        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.labels'
        ]
        
        creds_file = GMAIL_DIR / "credentials.json"
        if not creds_file.exists():
            print("❌ credentials.json não encontrado!")
            return False
        
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        
        print("\n🌐 Abrindo navegador para autorização...")
        print("   Autorize o acesso e volte aqui.\n")
        
        creds = flow.run_local_server(port=8080)
        
        # Salvar tokens
        for dir_path in [GMAIL_DIR, CALENDAR_DIR]:
            token_path = dir_path / "token.pickle"
            with open(token_path, 'wb') as f:
                pickle.dump(creds, f)
            print(f"✅ Token salvo: {token_path}")
        
        # Testar Gmail
        print("\n📧 Testando Gmail...")
        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        print(f"   ✅ Conectado como: {profile['emailAddress']}")
        
        # Testar Calendar
        print("\n📅 Testando Calendar...")
        calendar = build('calendar', 'v3', credentials=creds)
        events = calendar.events().list(calendarId='primary', maxResults=1).execute()
        print(f"   ✅ Calendar OK")
        
        return True
        
    except ImportError:
        print("❌ Bibliotecas não instaladas!")
        print("   Execute: pip install google-auth-oauthlib google-api-python-client")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    print_banner()
    
    # Verificar credenciais existentes
    creds = check_existing_creds()
    
    if creds:
        print(f"\n✅ Credenciais encontradas: {creds}")
        choice = input("\nDeseja pular para autenticação? (s/n): ").lower()
        
        if choice == 's':
            copy_credentials()
            authenticate()
            return
    
    print("\n📋 Iniciando configuração passo-a-passo...")
    print("   Siga as instruções para cada etapa.\n")
    
    setup_step_by_step()
    
    print("\n" + "="*60)
    print("📂 Verificando credenciais...")
    print("="*60)
    
    if copy_credentials():
        print("\n" + "="*60)
        print("🔐 Iniciando autenticação OAuth...")
        print("="*60)
        
        if authenticate():
            print("""
╔════════════════════════════════════════════════════════════════╗
║                    ✅ SETUP COMPLETO!                          ║
╚════════════════════════════════════════════════════════════════╝

Agora você pode usar:

📧 Gmail:
   /gmail listar
   /gmail treinar confirmar  ← Treina IA antes de limpar!

📅 Calendar:
   /calendar listar
   /calendar criar reunião amanhã

Ou via terminal:
   python email_cleaner_runner.py
""")
        else:
            print("\n⚠️ Autenticação não completada. Tente novamente.")
    else:
        print("\n⚠️ Credenciais não configuradas. Siga o passo-a-passo.")

if __name__ == "__main__":
    main()
