#!/usr/bin/env python3
"""
Script para completar autenticação OAuth e buscar currículos
Este é um wrapper interativo para o interactive_auth.py no servidor
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                  AUTENTICAÇÃO GOOGLE DRIVE - ETAPA FINAL                   ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 INSTRUÇÕES:

1️⃣  Procure na URL redirecionada pelo Google o seguinte padrão:
   
   http://localhost:8080/?code=4/0AfJohX...&state=...
                              ↑
                         COPIE DAQUI

2️⃣  Procure especificamente pelo "code=" e copie até o próximo "&" ou fim da URL

Exemplo:
   URL completa:  http://localhost:8080/?code=4/0AfJohXx3wA9B_l2K3m4n5o6p7q8r9s&state=abc123
   Código a copiar: 4/0AfJohXx3wA9B_l2K3m4n5o6p7q8r9s

3️⃣  Cole o código abaixo:
""")

    code = input("\n🔑 Cole o código de autorização: ").strip()
    
    if not code:
        print("❌ Código vazio!")
        return False
    
    if len(code) < 10:
        print("⚠️  O código parece muito curto. Verifique se copiou corretamente.")
        confirm = input("Deseja continuar mesmo assim? (s/n): ").strip().lower()
        if confirm != 's':
            return False
    
    print("\n🔄 Enviando código para o servidor...")
    print(f"📝 Código recebido: {code[:20]}...{code[-10:]}")
    
    # Executar script remoto com o código
    try:
        # Usar SSH para executar o script com o código via echo
        cmd = f"""
ssh homelab@192.168.15.2 'cd /home/homelab/myClaude && python3 << EOF
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json
from datetime import datetime

CREDS_FILE = Path("/home/homelab/myClaude/credentials.json")
DRIVE_DIR = Path("/home/homelab/myClaude/drive_data")
DRIVE_TOKEN = DRIVE_DIR / "token.json"
DRIVE_DIR.mkdir(exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels"
]

print("🔄 Processando autorização...")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")

try:
    flow.fetch_token(code="{code}")
    creds = flow.credentials
    
    with open(DRIVE_TOKEN, "w") as f:
        json.dump({{
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }}, f, indent=2)
    
    print("✅ Token salvo com sucesso!")
    print("🔍 Buscando currículos...")
    
    from googleapiclient.discovery import build
    
    drive = build("drive", "v3", credentials=creds)
    
    terms = ["curriculo", "currículo", "curriculum", "cv", "resume"]
    all_files = []
    
    for term in terms:
        q = f"name contains '{term}' and trashed=false"
        try:
            results = drive.files().list(
                q=q,
                pageSize=10,
                orderBy="modifiedTime desc",
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)"
            ).execute()
            
            files = results.get("files", [])
            if files:
                print(f"✓ '{term}': {{len(files)}} arquivo(s)")
                all_files.extend(files)
        except:
            pass
    
    if not all_files:
        print("❌ Nenhum currículo encontrado")
    else:
        unique = {{f["id"]: f for f in all_files}}
        sorted_files = sorted(unique.values(), key=lambda f: f.get("modifiedTime", ""), reverse=True)
        
        print(f"\\n📊 CURRÍCULOS ENCONTRADOS: {{len(sorted_files)}}")
        print("=" * 80)
        
        for i, f in enumerate(sorted_files[:5], 1):
            name = f.get("name", "Sem nome")
            size = int(f.get("size", 0)) / 1024
            mod = f.get("modifiedTime", "")
            link = f.get("webViewLink", "N/A")
            
            marker = "⭐ MAIS RECENTE" if i == 1 else ""
            print(f"\\n[{{i}}] {{name}} {{marker}}")
            print(f"    Tamanho: {{size:.1f}} KB | Modificado: {{mod[:10]}}")
            print(f"    🔗 {{link}}")

except Exception as e:
    print(f"❌ Erro: {{type(e).__name__}}: {{e}}")
    exit(1)
EOF
'
"""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        print("\n" + "=" * 80)
        print("📤 RESPOSTA DO SERVIDOR:")
        print("=" * 80)
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ Avisos:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n✅ AUTENTICAÇÃO COMPLETADA COM SUCESSO!")
            print("\n💾 Token salvo em: /home/homelab/myClaude/drive_data/token.json")
            return True
        else:
            print(f"\n❌ Erro durante a autenticação (código: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout - o servidor demorou muito para responder")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
