#!/usr/bin/env python3
"""
Gerar URL de autenticação do Google Drive
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json

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

print("=" * 80)
print("🔐 GERAR URL DE AUTENTICAÇÃO GOOGLE")
print("=" * 80)

# Ler as credenciais
with open(CREDS_FILE) as f:
    client_config = json.load(f)

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

# Gerar URL com os parâmetros corretos
auth_url, _ = flow.authorization_url(
    access_type='offline',
    prompt='consent'
)

print("\n📋 URL DE AUTENTICAÇÃO:\n")
print(auth_url)

print("\n" + "=" * 80)
print("📌 INSTRUÇÕES:")
print("=" * 80)
print("""
1. Copie a URL acima
2. Abra em um navegador (no seu computador local)
3. Autorize o Shared Assistant
4. Você será redirecionado para uma URL com '?code=XXX'
5. Copie o código (a parte depois de 'code=')
6. Execute: python3 complete_auth.py <CODIGO>

Se não conseguir abrir, use outro redirect_uri:
   - urn:ietf:wg:oauth:2.0:oob (copia/cola código diretamente)
""")
