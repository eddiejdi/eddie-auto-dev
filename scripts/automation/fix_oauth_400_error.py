#!/usr/bin/env python3
"""
🔧 Solução para Erro OAuth 400: invalid_request
Problema: redirect_uri não corresponde entre credenciais e URL OAuth

Estratégia de Correção:
1. Usar redirect_uri correto configurado: http://localhost
2. Se falhar, usar fluxo manual sem servidor
3. Se ainda falhar, oferecer alternativas
"""

import subprocess
import sys


def print_section(title):
    print(f"\n{'═' * 80}")
    print(f"  {title}")
    print(f"{'═' * 80}\n")

def create_oauth_script_with_redirect():
    """Create script that uses the correct redirect_uri"""
    
    script = '''
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

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

print("\\n" + "="*70)
print("🔐 AUTENTICAÇÃO OAUTH - CORREÇÃO DE redirect_uri")
print("="*70)

flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)

# Estratégia 1: Tentar porta 80 (redirect_uri oficial é http://localhost)
print("\\n📋 Etapa 1: Tentando porta 80 (redirect_uri padrão)...")

try:
    creds = flow.run_local_server(port=80, open_browser=False)
    print("✅ Sucesso! Token obtido via porta 80")
    
except PermissionError as e:
    print("⚠️  Porta 80 requer sudo (permissão negada)")
    print("\\n📋 Etapa 2: Usando fluxo manual alternativo...")
    
    # Estratégia 2: Fluxo manual
    auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
    
    print(f"\\n🔗 URL DE AUTORIZAÇÃO (copie no navegador):\\n{auth_url}")
    
    auth_code = input("\\n🔑 Cole o código COMPLETO (começando com '4/0Af'): ").strip()
    
    if not auth_code:
        print("❌ Código vazio!")
        exit(1)
    
    try:
        print("🔄 Processando código...")
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        print("✅ Sucesso! Token obtido via código manual")
    except Exception as e:
        print(f"❌ Erro ao processar código: {e}")
        print("\\nDicas:")
        print("  • Certifique-se de copiar o código INTEIRO")
        print("  • Inclua 'state=' se estiver na URL")
        print("  • Tente novamente e copie desde 'code=' até o final")
        exit(1)

except Exception as e:
    print(f"❌ Erro inesperado: {e}")
    print("\\nPor favor, tente novamente.")
    exit(1)

# Salvar token
print("\\n💾 Salvando token...")
with open(DRIVE_TOKEN, "w") as f:
    json.dump({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }, f, indent=2)

print("✅ Token salvo em:", DRIVE_TOKEN)

# Buscar currículos
print("\\n📂 BUSCANDO CURRÍCULOS...")
print("="*70)

try:
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
                print(f"✓ '{term}': {len(files)} arquivo(s)")
                all_files.extend(files)
        except:
            pass
    
    if not all_files:
        print("\\n❌ Nenhum currículo encontrado")
        exit(1)
    
    # Remover duplicatas e ordenar
    unique = {f["id"]: f for f in all_files}
    sorted_files = sorted(unique.values(), 
                         key=lambda f: f.get("modifiedTime", ""), 
                         reverse=True)
    
    print(f"\\n📊 Total de currículos encontrados: {len(sorted_files)}")
    print("="*70)
    
    for i, f in enumerate(sorted_files[:5], 1):
        name = f.get("name", "Sem nome")
        size = int(f.get("size", 0)) / 1024
        mod_time = f.get("modifiedTime", "")
        link = f.get("webViewLink", "N/A")
        
        marker = "⭐ MAIS RECENTE" if i == 1 else ""
        print(f"\\n[{i}] {name} {marker}")
        print(f"    Tamanho: {size:.1f} KB")
        print(f"    Modificado: {mod_time[:10]}")
        print(f"    🔗 {link}")
    
    print("\\n" + "="*70)
    print("✅ SUCESSO! Currículos listados acima.")
    
except Exception as e:
    print(f"❌ Erro ao buscar currículos: {e}")
    exit(1)
'''
    
    return script

def main():
    print_section("🔧 CORRIGINDO ERRO: Invalid Redirect URI")
    
    print("""
PROBLEMA IDENTIFICADO:
  Erro: 400 invalid_request (flowName=GeneralOAuthFlow)
  Causa: redirect_uri não corresponde
  
  Credenciais Google:  http://localhost
  URL anterior:        http://localhost:8080
  
SOLUÇÃO:
  ✅ Usar redirect_uri correto (sem porta)
  ✅ Ou usar fluxo completamente manual
  ✅ Buscar currículos automaticamente
""")
    
    print_section("Executando Correção")
    
    script = create_oauth_script_with_redirect()
    
    # Deploy and execute
    cmd = f"""ssh homelab@192.168.15.2 "cd /home/homelab/myClaude && python3 << 'ENDPYTHON'
{script}
ENDPYTHON
" 2>&1
"""
    
    print("🔄 Conectando ao servidor e iniciando autenticação...")
    print("   (Se pedir por senha/código, siga as instruções)\n")
    
    result = subprocess.run(cmd, shell=True, timeout=180)
    
    print("\n" + "="*80)
    if result.returncode == 0:
        print("✅ PROCESSO CONCLUÍDO COM SUCESSO!")
        print("="*80)
        print("""
Próximas ações:
  1. Verifique a lista de currículos acima
  2. Clique nos links para abrir no Google Drive
  3. Atualize com experiência B3 S.A. recente
  4. Salve novamente
""")
    else:
        print("❌ ERRO DURANTE O PROCESSO")
        print("="*80)
        print("""
Se receber erro novamente:
  1. Verifique se está autorizado no Google
  2. Tente abrir a URL manualmente no navegador
  3. Copie o código completo (com "4/0Af...")
  4. Repita o processo
        """)
    
    return result.returncode == 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Processo interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro fatal: {e}")
        sys.exit(1)
