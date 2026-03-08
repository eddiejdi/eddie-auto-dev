#!/usr/bin/env python3
"""
Buscar currículo no Google Drive com autenticação automática via command-line
Usa stdin para inserir o código de autorização
"""
import json
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime

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

def authenticate():
    """Autenticar com Google"""
    print("=" * 80)
    print("🔐 AUTENTICAÇÃO GOOGLE - BUSCAR CURRÍCULO")
    print("=" * 80)
    
    # Se já tem token válido
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
                pass
    
    if not CREDS_FILE.exists():
        print(f"❌ Arquivo credentials.json não encontrado: {CREDS_FILE}")
        sys.exit(1)
    
    print("\n🔗 Iniciando autenticação...")
    print("   Abrindo navegador para autorização...\n")
    
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    
    # Usar servidor local na porta 8080
    try:
        creds = flow.run_local_server(port=8080, open_browser=False)
    except OSError:
        # Se porta estiver ocupada, tentar outra
        try:
            creds = flow.run_local_server(port=8888, open_browser=False)
        except OSError:
            creds = flow.run_local_server(port=9090, open_browser=False)
    
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
    
    print(f"\n✅ Token salvo em: {DRIVE_TOKEN}")
    return creds

def search_resume(creds):
    """Buscar currículo no Drive"""
    print("\n" + "=" * 80)
    print("📂 BUSCANDO CURRÍCULO NO GOOGLE DRIVE")
    print("=" * 80)
    
    drive = build('drive', 'v3', credentials=creds)
    
    terms = ['curriculo', 'currículo', 'curriculum', 'cv', 'resume']
    doc_types = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'application/vnd.google-apps.document'
    ]
    
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
            print(f"⚠️  '{term}': {str(e)[:50]}")
    
    if not all_files:
        print("\n❌ Nenhum currículo encontrado")
        return
    
    # Remover duplicatas
    unique = {f['id']: f for f in all_files}
    sorted_files = sorted(unique.values(), 
                         key=lambda f: f.get('modifiedTime', ''), 
                         reverse=True)
    
    print(f"\n📊 Total: {len(sorted_files)} currículo(s) único(s)")
    print("=" * 80)
    print("📄 CURRÍCULOS ENCONTRADOS:")
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
    print(f"  Nome: {most_recent.get('name')}")
    print(f"  ID: {most_recent.get('id')}")
    print(f"  Link: {most_recent.get('webViewLink')}")
    
    # Salvar info
    with open('/tmp/resume_info.json', 'w') as f:
        json.dump({
            'nome': most_recent.get('name'),
            'id': most_recent.get('id'),
            'link': most_recent.get('webViewLink')
        }, f, indent=2)
    
    print("\n✅ Informações salvas em /tmp/resume_info.json")

if __name__ == "__main__":
    creds = authenticate()
    search_resume(creds)
