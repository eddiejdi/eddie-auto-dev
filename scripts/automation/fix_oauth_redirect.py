#!/usr/bin/env python3
"""
Corrigir erro OAuth 400: invalid_request
Problema: redirect_uri não corresponde

Solução: Usar localhost sem porta explícita (http://localhost/)
"""

import subprocess
import sys

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                       🔧 CORRIGINDO ERRO OAUTH 400                         ║
╚════════════════════════════════════════════════════════════════════════════╝

⚠️  PROBLEMA IDENTIFICADO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Erro: 400 invalid_request
Causa: redirect_uri não corresponde

  Configurado no Google Cloud:  http://localhost
  Url usado no sistema:         http://localhost:8080

✅ SOLUÇÃO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Vou criar um novo fluxo que:
1. Usa o redirect_uri correto: http://localhost
2. Sem porta explícita (a porta 80 é implícita)
3. Mantém um servidor local mínimo na porta 80

⚠️  AVISO: Pode exigir sudo para porta 80
   Se não tiver permissão, usaremos uma abordagem alternativa

""")
    
    # Opção 1: Tentar com porta 80 (requer sudo)
    print("🔍 Tentando Opção 1: Servidor na porta 80...")
    
    code = """
import subprocess
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

CREDS_FILE = Path('/home/homelab/myClaude/credentials.json')
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

print("🔄 Iniciando fluxo OAuth com redirect_uri correto... ")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)

# Tentar port 80 (padrão HTTP)
try:
    print("Tentando porta 80...")
    creds = flow.run_local_server(port=80, open_browser=False)
    print("✅ Sucesso! Token obtido.")
except PermissionError:
    print("❌ Permissão negada para porta 80 (requer sudo)")
    print("\\nTentando Opção 2: sem servidor local (fluxo manual)...")
    
    # Opção 2: Fluxo manual sem servidor
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    print(f"\\n📋 URL de autorização:\\n{auth_url}")
    code = input("\\n🔑 Cole o código após autorizar: ").strip()
    
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        print("✅ Token obtido com sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
        exit(1)
"""
    
    # Executar no servidor
    cmd = f"""ssh homelab@192.168.15.2 "cd /home/homelab/myClaude && python3 << 'ENDPYTHON'
{code}
ENDPYTHON
"
"""
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"\n❌ Erro durante execução (código {result.returncode})")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
