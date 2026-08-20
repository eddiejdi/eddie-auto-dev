#!/usr/bin/env python3
"""
Autenticar e buscar currículo automaticamente
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

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

def main():
    print("=" * 80)
    print("🔐 AUTENTICAÇÃO GOOGLE + BUSCA DE CURRÍCULO")
    print("=" * 80)
    
    # Carregar ou criar credenciais
    creds = None
    
    # Se token existe, tentar usar
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
    
    # Se não temos credenciais ou não são válidas
    if not creds or not creds.valid:
        print("\n🔗 Iniciando autenticação OAuth...")
        print("   Uma janela do navegador será aberta.")
        print("   Autorize o acesso e volte aqui.\n")
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_FILE),
                SCOPES
            )
            
            # Tentar múltiplas portas
            for port in [8080, 8888, 9090, 3000, 5000]:
                try:
                    print(f"Tentando porta {port}...")
                    creds = flow.run_local_server(port=port, open_browser=False)
                    break
                except OSError:
                    if port == 5000:
                        raise
                    continue
            
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
            
        except Exception as e:
            print(f"❌ Erro na autenticação: {e}")
            return False
    else:
        print("✅ Token válido encontrado!")
    
    # Buscar currículo
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
                print(f"⚠️  '{term}': {str(e)[:50]}")
        
        if not all_files:
            print("\n❌ Nenhum currículo encontrado")
            return False
        
        # Remover duplicatas
        unique = {f['id']: f for f in all_files}
        sorted_files = sorted(unique.values(), 
                             key=lambda f: f.get('modifiedTime', ''), 
                             reverse=True)
        
        print(f"\n📊 Total: {len(sorted_files)} currículo(s) encontrado(s)")
        print("=" * 80)
        print("📄 CURRÍCULOS:")
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
        print(f"📄 Nome: {most_recent.get('name')}")
        print(f"🔗 Link: {most_recent.get('webViewLink')}")
        
        # Salvar info
        with open('/tmp/resume_info.json', 'w') as f:
            json.dump({
                'nome': most_recent.get('name'),
                'id': most_recent.get('id'),
                'link': most_recent.get('webViewLink'),
                'tamanho_kb': size,
                'modificado': mod_str
            }, f, indent=2)
        
        print("\n✅ Informações salvas!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao buscar currículo: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
