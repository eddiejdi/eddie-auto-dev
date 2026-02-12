#!/usr/bin/env python3
"""
Autenticação interativa - insira o código manualmente
"""
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime
import sys

CREDS_FILE = Path('/home/homelab/myClaude/credentials.json')
DRIVE_DIR = Path('/home/homelab/myClaude/drive_data')
DRIVE_TOKEN = DRIVE_DIR / 'token.json'
DRIVE_DIR.mkdir(exist_ok=True)

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

def get_or_refresh_credentials():
    """Obter ou atualizar credenciais"""
    
    # Se existe token válido, retornar
    if DRIVE_TOKEN.exists():
        with open(DRIVE_TOKEN) as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', SCOPES)
        )
        
        if creds.valid:
            print("✅ Token válido encontrado!")
            return creds
        
        if creds.refresh_token:
            try:
                print("🔄 Renovando token...")
                creds.refresh(Request())
                print("✅ Token renovado!")
                return creds
            except:
                print("⚠️  Falha ao renovar token, necessário reautenticar")
    
    # Nova autenticação
    print("\n" + "=" * 80)
    print("🔐 NOVA AUTENTICAÇÃO REQUERIDA")
    print("=" * 80)
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDS_FILE),
        SCOPES
    )
    
    # Gerar URL sem servidor local
    auth_url, state = flow.authorization_url(
        prompt='consent',
        access_type='offline'
    )
    
    print("""
📋 PASSO 1: Copie e abra esta URL no seu navegador:
""")
    print(auth_url)
    
    print("""
📋 PASSO 2: Após autorizar, você será redirecionado para uma URL contendo '?code=...'

📋 PASSO 3: Copie o CÓDIGO (a parte depois de 'code=')

Exemplo:
  URL: http://localhost:8080/?code=4/0AfJohX...&state=...
  CÓDIGO: 4/0AfJohX...
""")
    
    # Aguardar input do código
    auth_code = input("\n🔑 Cole o código longo aqui: ").strip()
    
    if not auth_code:
        print("❌ Código vazio!")
        return None
    
    try:
        print("\n🔄 Processando autorização...")
        # Trocar o código por token
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        
        # Salvar token
        with open(DRIVE_TOKEN, 'w') as f:
            json.dump({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }, f, indent=2)
        
        print("✅ Token salvo!")
        return creds
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def search_resume(creds):
    """Buscar currículo"""
    print("\n" + "=" * 80)
    print("📂 BUSCANDO CURRÍCULO NO GOOGLE DRIVE")
    print("=" * 80)
    
    try:
        drive = build('drive', 'v3', credentials=creds)
        
        terms = ['curriculo', 'currículo', 'curriculum', 'cv', 'resume']
        all_files = []
        
        for term in terms:
            q = f"name contains '{term}' and trashed=false"
            try:
                results = drive.files().list(
                    q=q,
                    pageSize=10,
                    orderBy='modifiedTime desc',
                    fields='files(id, name, mimeType, size, modifiedTime, webViewLink)'
                ).execute()
                
                files = results.get('files', [])
                if files:
                    print(f"✓ '{term}': {len(files)} arquivo(s)")
                    all_files.extend(files)
            except Exception as e:
                print(f"⚠️  '{term}': erro")
        
        if not all_files:
            print("\n❌ Nenhum currículo encontrado")
            return False
        
        # Remover duplicatas
        unique = {f['id']: f for f in all_files}
        sorted_files = sorted(unique.values(), 
                             key=lambda f: f.get('modifiedTime', ''), 
                             reverse=True)
        
        print(f"\n📊 Total: {len(sorted_files)} currículo(s)")
        print("=" * 80)
        
        for i, f in enumerate(sorted_files[:10], 1):
            name = f.get('name')
            size = int(f.get('size', 0)) / 1024
            mod_time = f.get('modifiedTime', '')
            
            try:
                dt = datetime.fromisoformat(mod_time.replace('Z', '+00:00'))
                mod_str = dt.strftime('%d/%m/%Y %H:%M')
            except:
                mod_str = mod_time
            
            marker = '⭐ MAIS RECENTE' if i == 1 else ''
            print(f"\n[{i}] {name} {marker}")
            print(f"    Tamanho: {size:.1f} KB")
            print(f"    Modificado: {mod_str}")
            print(f"    Link: {f.get('webViewLink', 'N/A')}")
        
        print("\n" + "=" * 80)
        print("✅ CURRÍCULO MAIS RECENTE:")
        print("=" * 80)
        
        most_recent = sorted_files[0]
        print(f"📄 {most_recent.get('name')}")
        print(f"🔗 {most_recent.get('webViewLink')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    creds = get_or_refresh_credentials()
    
    if creds:
        search_resume(creds)
    else:
        print("\n❌ Falha na autenticação")
        sys.exit(1)
