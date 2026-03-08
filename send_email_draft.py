#!/usr/bin/env python3
"""
Envia o email draft para Gmail usando a Gmail API (OAuth).
"""
import base64
import subprocess
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SENDER_EMAIL = "edenilson.adm@gmail.com"
RECIPIENT_EMAIL = "edenilson.adm@gmail.com"
SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/shared/secrets_agent/audit.db"

def get_secret_from_agent(secret_name: str) -> str:
    """Fetch secret from Secrets Agent."""
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64, sys
conn = sqlite3.connect('{SECRETS_AGENT_TOKEN_PATH}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='{secret_name}'")
row = c.fetchone()
conn.close()
if not row:
    print('NOT_FOUND')
    sys.exit(0)
try:
    print(base64.b64decode(row[0]).decode())
except:
    print(row[0])
PY"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"failed to fetch secret: {res.stderr}")
    out = res.stdout.strip()
    if out == "NOT_FOUND":
        raise KeyError(f"secret not found: {secret_name}")
    return out

def save_draft_to_gmail(eml_bytes: bytes, creds) -> bool:
    """Save email as draft in Gmail (fallback)."""
    try:
        print("💾 Salvando como draft no Gmail...")
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        raw_message = base64.urlsafe_b64encode(eml_bytes).decode()
        result = gmail_service.users().drafts().create(
            userId='me', 
            body={'message': {'raw': raw_message}}
        ).execute()
        
        print(f"✅ Email salvo como draft no Gmail!")
        print(f"   Draft ID: {result.get('id')}")
        print(f"   Verifique sua caixa de Rascunhos para revisar e enviar")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao salvar draft: {e}")
        return False

def send_email(eml_file: str):
    """Send email from EML file via Gmail API."""
    print(f"📧 Enviando email de {eml_file}...")
    
    # Read EML file
    eml_path = Path(eml_file)
    if not eml_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {eml_file}")
    
    with open(eml_path, 'rb') as f:
        eml_bytes = f.read()
    
    # Get OAuth token
    print("🔐 Obtendo credenciais do Gmail...")
    try:
        gmail_token_json = get_secret_from_agent("google/gmail_token")
        gmail_data = json.loads(gmail_token_json)
    except Exception as e:
        print(f"❌ Erro ao obter credenciais: {e}")
        return False
    
    # Create credentials
    creds = Credentials(
        token=gmail_data.get('access_token'),
        refresh_token=gmail_data.get('refresh_token'),
        token_uri=gmail_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=gmail_data.get('client_id'),
        client_secret=gmail_data.get('client_secret'),
        scopes=['https://www.googleapis.com/auth/gmail.send'],
    )
    
    # Refresh if expired
    if creds.expired or not creds.valid:
        print("🔄 Tentando refrescar token...")
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"⚠️  Escopo inválido no token: {e}")
            print("   Salvando como draft ao invés...")
            return save_draft_to_gmail(eml_bytes, creds)
    
    # Build Gmail API client
    print("🔗 Conectando ao Gmail...")
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # Send email
    try:
        print(f"📬 Enviando para {RECIPIENT_EMAIL}...")
        raw_message = base64.urlsafe_b64encode(eml_bytes).decode()
        result = gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        
        print(f"✅ Email enviado com sucesso!")
        print(f"   Message ID: {result.get('id')}")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao enviar via Gmail API: {e}")
        print(f"   Tentando salvar como draft...")
        return save_draft_to_gmail(eml_bytes, creds)

if __name__ == '__main__':
    import sys
    
    # Use latest draft if not specified
    eml_file = sys.argv[1] if len(sys.argv) > 1 else 'draft_20260211_163930.eml'
    
    success = send_email(eml_file)
    sys.exit(0 if success else 1)
