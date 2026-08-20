#!/usr/bin/env python3
"""Script simplificado para buscar currículo no Google Drive"""
import json
import sys
from pathlib import Path

# Adicionar diretório ao path
sys.path.insert(0, '/home/homelab/myClaude')

def buscar_curriculo_drive():
    """Busca currículo no Drive reutilizando token do Gmail"""
    print("📂 Buscando currículo no Google Drive...")
    print("="*80)
    
    # Tentar usar token do Gmail
    gmail_token_path = Path('/home/homelab/myClaude/gmail_data/token.json')
    
    if not gmail_token_path.exists():
        print(f"❌ Token não encontrado: {gmail_token_path}")
        return False
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Carregar token
        with open(gmail_token_path) as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', [])
        )
        
        print("✓ Token carregado")
        print(f"  Escopos: {', '.join(creds.scopes[:2])}...")
        
        # Verificar se tem escopo do Drive
        has_drive_scope = any('drive' in scope for scope in creds.scopes)
        
        if not has_drive_scope:
            print("\n⚠️  Token não tem escopos do Drive")
            print("  É necessário reautenticar com os novos escopos.")
            print("\n  Execute: python3 setup_google_apis.py")
            return False
        
        # Criar serviço Drive
        print("\n📂 Conectando ao Google Drive...")
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Buscar por currículo
        search_terms = ['curriculo', 'currículo', 'curriculum', 'cv', 'resume']
        
        # MIME types para documentos
        doc_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'application/vnd.google-apps.document'
        ]
        
        print("\n🔍 Buscando arquivos...")
        
        all_files = []
        
        for term in search_terms:
            # Construir query
            q_parts = [f"name contains '{term}'"]
            q_parts.append("trashed=false")
            
            mime_conditions = [f"mimeType='{mt}'" for mt in doc_types]
            q_parts.append(f"({' or '.join(mime_conditions)})")
            
            q_string = ' and '.join(q_parts)
            
            try:
                results = drive_service.files().list(
                    q=q_string,
                    pageSize=10,
                    orderBy='modifiedTime desc',
                    fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink)"
                ).execute()
                
                files = results.get('files', [])
                
                if files:
                    print(f"  ✓ '{term}': {len(files)} arquivo(s)")
                    all_files.extend(files)
                
            except Exception as e:
                print(f"  ⚠️  Erro ao buscar '{term}': {e}")
        
        if not all_files:
            print("\n❌ Nenhum currículo encontrado")
            return False
        
        # Remover duplicatas
        unique_files = {f['id']: f for f in all_files}
        all_files = sorted(unique_files.values(), 
                          key=lambda f: f.get('modifiedTime', ''), 
                          reverse=True)
        
        print(f"\n📊 Total: {len(all_files)} arquivo(s) único(s)")
        print("\n" + "="*80)
        print("📄 CURRÍCULOS ENCONTRADOS:")
        print("="*80)
        
        from datetime import datetime
        
        for i, file in enumerate(all_files[:10], 1):
            name = file.get('name', 'Sem nome')
            size = int(file.get('size', 0)) / 1024  # KB
            mod_time = file.get('modifiedTime', '')
            
            if mod_time:
                try:
                    dt = datetime.fromisoformat(mod_time.replace('Z', '+00:00'))
                    mod_str = dt.strftime('%d/%m/%Y %H:%M')
                except:
                    mod_str = mod_time
            else:
                mod_str = 'N/A'
            
            print(f"\n[{i}] {name}")
            print(f"    Tamanho: {size:.1f} KB")
            print(f"    Modificado: {mod_str}")
            print(f"    Link: {file.get('webViewLink', 'N/A')}")
            
            if i == 1:
                print("\n    ⭐ MAIS RECENTE")
        
        # Mostrar o mais recente
        most_recent = all_files[0]
        
        print("\n" + "="*80)
        print("✅ CURRÍCULO MAIS RECENTE:")
        print("="*80)
        print(f"  Nome: {most_recent.get('name')}")
        print(f"  ID: {most_recent.get('id')}")
        print(f"  Link: {most_recent.get('webViewLink')}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        print("\nInstale: pip install google-api-python-client google-auth")
        return False
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    buscar_curriculo_drive()
