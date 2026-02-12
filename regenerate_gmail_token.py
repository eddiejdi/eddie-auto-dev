#!/usr/bin/env python3
"""
Regenerate Gmail OAuth token with correct scopes (gmail.modify).
Salva o novo token no Secrets Agent.
"""
import json
import subprocess
import webbrowser
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Project ID
PROJECT_ID = "home-lab-483803"

# Scopes needed: send, modify, read
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # Full control
    'https://www.googleapis.com/auth/gmail.send',     # Send emails
    'https://www.googleapis.com/auth/drive',           # Drive access
]

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_DB = "/var/lib/eddie/secrets_agent/audit.db"

def get_credentials_json():
    """Get the OAuth credentials.json from Secrets Agent."""
    print("📥 Buscando credentials.json do Secrets Agent...")
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64, json
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='google/oauth_client_installed' AND field='credentials_json'")
row = c.fetchone()
conn.close()
if not row:
    print('NOT_FOUND')
else:
    try:
        print(base64.b64decode(row[0]).decode())
    except:
        print(row[0])
PY"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0 or "NOT_FOUND" in res.stdout:
        raise RuntimeError("credentials.json não encontrado no Secrets Agent")
    
    # Extract JSON from output
    output = res.stdout.strip()
    # Find JSON part
    json_start = output.find('{')
    if json_start == -1:
        raise RuntimeError(f"No JSON found in output: {output}")
    
    return json.loads(output[json_start:])

def regenerate_token():
    """Regenerate OAuth token with new scopes."""
    print("\n" + "="*70)
    print("🔄 REGENERANDO TOKEN GMAIL COM ESCOPOS CORRETOS")
    print("="*70 + "\n")
    
    # Get existing credentials.json
    creds_json = get_credentials_json()
    print(f"✅ Credenciais obtidas do Secrets Agent")
    print(f"   Project ID: {creds_json.get('installed', {}).get('client_id', 'N/A')[:20]}...")
    
    # Create temp file with credentials
    temp_creds = Path("/tmp/credentials_temp.json")
    with open(temp_creds, 'w') as f:
        json.dump(creds_json, f)
    
    # Create flow with NEW scopes
    print(f"\n🔐 Criando flow OAuth com escopos: {SCOPES}")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(temp_creds),
        scopes=SCOPES,
        redirect_uri='http://localhost:8080'
    )
    
    print("\n📱 Abrindo navegador para autenticação...")
    print("(Se o navegador não abrir, acesse: http://localhost:8080)")
    
    try:
        # Run local server
        creds = flow.run_local_server(
            port=8080,
            open_browser=True,
            authorization_prompt='consent'  # Force consent screen
        )
        
        print("\n✅ Autenticação concluída!")
        print(f"   Access Token: {creds.token[:30]}...")
        print(f"   Refresh Token: {creds.refresh_token[:30] if creds.refresh_token else 'N/A'}...")
        print(f"   Escopos: {creds.scopes}")
        
        return creds
    except Exception as e:
        print(f"❌ Erro na autenticação: {e}")
        return None
    finally:
        temp_creds.unlink()

def save_token_to_agent(creds) -> bool:
    """Save token to Secrets Agent."""
    print("\n💾 Salvando novo token no Secrets Agent...")
    
    # Prepare token data
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
    }
    
    token_json = json.dumps(token_data)
    import base64
    token_b64 = base64.b64encode(token_json.encode()).decode()
    
    # Save via SSH to Secrets Agent
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64, sys
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()

# Update or insert
token_b64 = '{token_b64}'
c.execute(
    "INSERT OR REPLACE INTO secrets_store (name, field, value) VALUES (?, ?, ?)",
    ('google/gmail_token', 'token_json', token_b64)
)
conn.commit()
conn.close()
print('OK')
PY"""
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode == 0 and "OK" in res.stdout:
        print("✅ Token salvo no Secrets Agent!")
        return True
    else:
        print(f"❌ Erro ao salvar: {res.stderr}")
        return False

def verify_token():
    """Verify token is correctly saved."""
    print("\n🔍 Verificando token salvo...")
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64, json
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='google/gmail_token'")
row = c.fetchone()
conn.close()

if row:
    try:
        data = json.loads(base64.b64decode(row[0]).decode())
        print("✅ Token verificado!")
        print(f"   Escopos: {data.get('scopes')}")
        print(f"   Token: {data.get('token')[:20]}...")
    except:
        print("❌ Erro ao decodificar token")
else:
    print("❌ Token não encontrado")
PY"""
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    print(res.stdout)
    return res.returncode == 0

def main():
    try:
        # Step 1: Regenerate token
        creds = regenerate_token()
        if not creds:
            print("❌ Falha ao regenerar token")
            return False
        
        # Step 2: Save to Secrets Agent
        if not save_token_to_agent(creds):
            print("❌ Falha ao salvar token")
            return False
        
        # Step 3: Verify
        verify_token()
        
        print("\n" + "="*70)
        print("✅ TOKEN GMAIL REGENERADO COM SUCESSO!")
        print("="*70)
        print("\n🎉 Próximo passo:")
        print("  Execute novamente: python3 send_via_curl.py")
        print("  Ou teste: python3 apply_real_job.py")
        
        return True
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
