#!/usr/bin/env python3
"""
Upload da imagem do scanner para Google Drive
Faz upload de scan_epson_l380_*.jpg para uma pasta no Drive
"""
import json
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# Configuração
CREDS_FILE = Path('/home/homelab/myClaude/credentials.json')
DRIVE_DIR = Path('/home/homelab/myClaude/drive_data')
DRIVE_TOKEN = DRIVE_DIR / 'token.json'
DRIVE_DIR.mkdir(exist_ok=True)

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

FOLDER_NAME = "Eddie Scanner Captures"

def get_or_create_credentials():
    """Obtém credenciais do token salvo ou cria novas por OAuth"""
    creds = None
    
    # Carregar token existente
    if DRIVE_TOKEN.exists():
        with open(DRIVE_TOKEN, 'r') as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', SCOPES)
        )
        
        # Renovar token se expirado
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(DRIVE_TOKEN, 'w') as f:
                    json.dump({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': list(creds.scopes) if creds.scopes else SCOPES
                    }, f, indent=2)
                print("🔄 Token renovado com sucesso")
            except Exception as e:
                print(f"⚠️ Erro ao renovar token: {e}")
                creds = None
    
    # Se não tem token, fazer autenticação nova
    if not creds or not creds.valid:
        if not CREDS_FILE.exists():
            print(f"❌ Arquivo credentials.json não encontrado: {CREDS_FILE}")
            print("   Execute: python3 get_auth_url.py")
            sys.exit(1)
        
        print("🔐 Autenticando com Google Drive via OAuth...")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=8080)
        
        # Salvar token
        with open(DRIVE_TOKEN, 'w') as f:
            json.dump({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': list(creds.scopes) if creds.scopes else SCOPES
            }, f, indent=2)
        print(f"✅ Token salvo em: {DRIVE_TOKEN}")
    
    return creds

def get_or_create_folder(service):
    """Procura ou cria pasta 'Eddie Scanner Captures' no Drive"""
    try:
        # Procurar por pasta existente
        query = f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()
        
        folders = results.get('files', [])
        if folders:
            folder_id = folders[0]['id']
            print(f"📁 Pasta encontrada: {FOLDER_NAME} (ID: {folder_id})")
            return folder_id
        
        # Criar pasta se não existir
        print(f"📁 Criando pasta: {FOLDER_NAME}")
        file_metadata = {
            'name': FOLDER_NAME,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        print(f"✅ Pasta criada: {folder_id}")
        return folder_id
    except Exception as e:
        print(f"❌ Erro ao gerenciar pasta: {e}")
        return None

def upload_file(service, file_path, folder_id):
    """Faz upload de um arquivo para o Google Drive"""
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ Arquivo não encontrado: {file_path}")
            return False
        
        file_metadata = {
            'name': file_path.name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(str(file_path), mimetype='image/jpeg', resumable=True)
        
        print(f"⬆️ Fazendo upload: {file_path.name}")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, name, size'
        ).execute()
        
        print(f"✅ Upload realizado com sucesso!")
        print(f"   Nome: {file.get('name')}")
        print(f"   Tamanho: {file.get('size', 0) / 1024:.1f} KB")
        print(f"   Link: {file.get('webViewLink')}")
        return True
    except Exception as e:
        print(f"❌ Erro ao fazer upload: {e}")
        return False

def main():
    # Encontrar arquivo de scan
    scan_files = list(Path.cwd().glob('scan_epson_l380_*.jpg'))
    if not scan_files:
        print("❌ Nenhum arquivo de scan encontrado (scan_epson_l380_*.jpg)")
        sys.exit(1)
    
    scan_file = sorted(scan_files, reverse=True)[0]  # Mais recente
    print(f"\n📸 Arquivo de scan: {scan_file.name}")
    print(f"   Tamanho: {scan_file.stat().st_size / 1024:.1f} KB")
    
    # Autenticar
    print("\n🔐 Autenticando com Google Drive...")
    creds = get_or_create_credentials()
    
    # Criar serviço
    service = build('drive', 'v3', credentials=creds)
    
    # Obter/Criar pasta
    print("\n📁 Gerenciando pasta do Drive...")
    folder_id = get_or_create_folder(service)
    if not folder_id:
        sys.exit(1)
    
    # Fazer upload
    print(f"\n📤 Upload para Google Drive")
    if upload_file(service, scan_file, folder_id):
        print("\n✅ SUCESSO! Imagem do scanner salva no Google Drive")
        print(f"   Pasta: {FOLDER_NAME}")
        print(f"   Arquivo: {scan_file.name}")
    else:
        print("\n❌ Falha ao fazer upload")
        sys.exit(1)

if __name__ == '__main__':
    main()
