#!/usr/bin/env python3
"""
Regenerar token Gmail com autorização manual (para ambientes sem navegador).
O usuário acessa a URL no navegador, autoriza, e cola o código aqui.
"""
import json
import subprocess
import base64
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_DB = "/var/lib/eddie/secrets_agent/audit.db"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive',
]

def get_credentials_json():
    """Get OAuth credentials.json from Secrets Agent."""
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
    
    output = res.stdout.strip()
    json_start = output.find('{')
    if json_start == -1:
        raise RuntimeError(f"No JSON found in output: {output}")
    
    return json.loads(output[json_start:])

def save_token_to_agent(creds) -> bool:
    """Save token to Secrets Agent."""
    print("\n💾 Salvando novo token no Secrets Agent...")
    
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
    }
    
    token_json = json.dumps(token_data)
    token_b64 = base64.b64encode(token_json.encode()).decode()
    
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64
conn = sqlite3.connect('{SECRETS_AGENT_DB}')
c = conn.cursor()
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
    """Verify saved token."""
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

def main():
    try:
        print("\n" + "="*70)
        print("🔄 REGENERANDO TOKEN GMAIL (Modo Manual)")
        print("="*70 + "\n")
        
        # Get credentials
        creds_json = get_credentials_json()
        print(f"✅ Credenciais obtidas do Secrets Agent")
        
        # Create temp file
        temp_creds = Path("/tmp/credentials_temp.json")
        with open(temp_creds, 'w') as f:
            json.dump(creds_json, f)
        
        # Create flow WITHOUT opening browser
        print(f"\n🔐 Criando flow OAuth com escopos: {SCOPES}\n")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(temp_creds),
            scopes=SCOPES,
            redirect_uri='http://localhost:8080'
        )
        
        # Get auth URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        print("📋 ACESSE ESTA URL NO SEU NAVEGADOR:\n")
        print(f"🔗 {auth_url}\n")
        print("="*70)
        print("\n1️⃣  Clique no link acima")
        print("2️⃣  Faça login no Gmail (se necessário)")
        print("3️⃣  Clique em 'Permitir' para autorizar")
        print("4️⃣  Você será redirecionado para http://localhost:8080")
        print("   (não se preocupe se não funcionar - a URL já tem o código)")
        print("5️⃣  Copie o CÓDIGO DE AUTORIZAÇÃO da URL")
        print("\n💡 Dica: Na URL final, procure por: ...?code=XXXX...")
        print("   (XXXX é o código que você precisa colar aqui)\n")
        
        # Get auth code from user
        auth_code = input("🔑 Cole o CÓDIGO DE AUTORIZAÇÃO: ").strip()
        if not auth_code:
            print("❌ Código não fornecido!")
            return False
        
        # Exchange code for token
        print(f"\n🔄 Trocando código por token...")
        try:
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            
            print("✅ Autenticação concluída!")
            print(f"   Access Token: {creds.token[:30]}...")
            print(f"   Refresh Token: {creds.refresh_token[:30] if creds.refresh_token else 'N/A'}...")
            print(f"   Escopos: {creds.scopes}")
            
        except Exception as e:
            print(f"❌ Erro ao trocar código por token: {e}")
            return False
        
        # Save to agent
        if not save_token_to_agent(creds):
            return False
        
        # Verify
        verify_token()
        
        print("\n" + "="*70)
        print("✅ TOKEN GMAIL REGENERADO COM SUCESSO!")
        print("="*70)
        print("\n🎉 Próximo passo:")
        print("  Execute: python3 send_via_curl.py")
        print("  Ou: python3 apply_real_job.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            Path("/tmp/credentials_temp.json").unlink()
        except:
            pass

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
