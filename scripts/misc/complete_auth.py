#!/usr/bin/env python3
"""
Completar autenticação com o código fornecido
Usage: python3 complete_auth.py <CODIGO>
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

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

if len(sys.argv) < 2:
    print("❌ Código não fornecido!")
    print("   Usage: python3 complete_auth.py <CODIGO>")
    sys.exit(1)

auth_code = sys.argv[1]

print("=" * 80)
print("🔐 COMPLETAR AUTENTICAÇÃO")
print("=" * 80)
print(f"\n📋 Código capturado: {auth_code[:20]}...")

try:
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    
    print("🔄 Processando autorização...")
    creds = flow.fetch_token(auth_code)
    
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
    
    print("\n✅ Autenticação completa!")
    print(f"   Token salvo em: {DRIVE_TOKEN}")
    
    # Agora buscar currículo
    print("\n" + "=" * 80)
    print("📂 BUSCANDO CURRÍCULO NO GOOGLE DRIVE")
    print("=" * 80)
    
    from datetime import datetime

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    
    creds_obj = Credentials(
        token=creds.token,
        refresh_token=creds.refresh_token,
        token_uri=creds.token_uri,
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        scopes=creds.scopes
    )
    
    drive = build('drive', 'v3', credentials=creds_obj)
    
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
        except:
            pass
    
    if not all_files:
        print("\n❌ Nenhum currículo encontrado")
        sys.exit(0)
    
    # Remover duplicatas
    unique = {f['id']: f for f in all_files}
    sorted_files = sorted(unique.values(), 
                         key=lambda f: f.get('modifiedTime', ''), 
                         reverse=True)
    
    print(f"\n📊 Total: {len(sorted_files)} currículo(s)")
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
    print(f"  Link: {most_recent.get('webViewLink')}")
    
except Exception as e:
    print(f"\n❌ Erro: {e}")
    sys.exit(1)
