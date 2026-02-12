#!/usr/bin/env python3
"""
Envia o email draft diretamente para a pasta de enviados via endpoint REST.
"""
import base64
import subprocess
import json
from pathlib import Path

SENDER_EMAIL = "edenilson.adm@gmail.com"
RECIPIENT_EMAIL = "edenilson.adm@gmail.com"
SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"

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

def send_via_curl(eml_file: str, access_token: str) -> bool:
    """Send email via curl and Gmail REST API."""
    try:
        print(f"📧 Enviando via REST API...")
        
        eml_path = Path(eml_file)
        if not eml_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {eml_file}")
        
        with open(eml_path, 'rb') as f:
            eml_bytes = f.read()
        
        raw_message = base64.urlsafe_b64encode(eml_bytes).decode()
        
        # Prepare JSON payload
        payload = json.dumps({"raw": raw_message})
        
        # Send via curl with Authorization header
        cmd = [
            "curl", "-X", "POST",
            "https://www.googleapis.com/gmail/v1/users/me/messages/send",
            "-H", f"Authorization: Bearer {access_token}",
            "-H", "Content-Type: application/json",
            "-d", payload
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        
        if res.returncode == 0:
            result = json.loads(res.stdout)
            if 'id' in result:
                print(f"✅ Email enviado com sucesso!")
                print(f"   Message ID: {result.get('id')}")
                return True
            else:
                print(f"⚠️  Resposta inexpect ada: {result}")
                return False
        else:
            print(f"❌ Erro no curl: {res.stderr}")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main(eml_file: str):
    """Main send function."""
    print(f"📧 Preparando para enviar {eml_file}...")
    
    try:
        # Get token
        print("🔐 Obtendo token...")
        gmail_token_json = get_secret_from_agent("google/gmail_token")
        gmail_data = json.loads(gmail_token_json)
        access_token = gmail_data.get('token') or gmail_data.get('access_token')
        
        if not access_token:
            raise ValueError("No access token found")
        
        # Try curl method
        success = send_via_curl(eml_file, access_token)
        
        if success:
            return True
        else:
            print("\n⚠️  Falha ao enviar. Instruções:")
            print("1. Abra https://mail.google.com/")
            print("2. Clique em 'Redigir'")
            print("3. Arraste o arquivo EML para a janela do navegador, ou:")
            print("4. Copie o conteúdo de draft_*.eml e cole em um novo email")
            print(f"\nArquivo disponível em: {Path(eml_file).absolute()}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        print(f"\n💥 Fallback: arquivo EML criado e pronto para enviar manualmente")
        return False

if __name__ == '__main__':
    import sys
    eml_file = sys.argv[1] if len(sys.argv) > 1 else 'draft_20260211_163930.eml'
    success = main(eml_file)
    sys.exit(0 if success else 1)
