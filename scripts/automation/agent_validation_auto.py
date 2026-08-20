#!/usr/bin/env python3
"""
🤖 Agent Validação Automática - Versão CLI
Executa no servidor e valida/processa código via stdin
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
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

def print_banner():
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + "🤖 AGENT VALIDAÇÃO AUTOMÁTICA - BUSCA DE CURRÍCULOS".center(78) + "║")
    print("╚" + "═"*78 + "╝\n")

def generate_auth_url():
    """Gera URL de autorização"""
    print("📋 Gerando URL de autorização Google...")
    
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
    
    print("✅ URL gerada\n")
    return auth_url, flow

def display_instructions(auth_url):
    """Mostra instruções ao usuário"""
    print("="*80)
    print("📌 INSTRUÇÕES")
    print("="*80 + "\n")
    
    print("1️⃣  COPIE ESTA URL:")
    print("-" * 80)
    print(auth_url)
    print("-" * 80 + "\n")
    
    print("2️⃣  ABRA NO SEU NAVEGADOR:")
    print("   • Cole a URL no endereço do navegador")
    print("   • OU clique se você conseguir (use Ctrl+Click)\n")
    
    print("3️⃣  FAÇA LOGIN:")
    print("   • Use sua conta Google")
    print("   • Que tenha seus currículos no Drive\n")
    
    print("4️⃣  AUTORIZE:")
    print("   • Clique em 'Permitir' ou 'Continuar'\n")
    
    print("5️⃣  COPIE O CÓDIGO:")
    print("   • Procure na URL por: code=4/0Af...")
    print("   • Copie tudo depois de 'code=' até o '&'\n")
    
    print("="*80 + "\n")

def capture_and_process_code(flow):
    """Captura código do usuário e processa"""
    
    print("🔑 PRÓXIMO PASSO: Cole o código\n")
    
    code = input("Cole o código copiado aqui: ").strip()
    
    if not code:
        print("\n❌ Código vazio!")
        return None
    
    if len(code) < 10:
        print("\n⚠️  O código parece muito curto")
        confirm = input("Deseja continuar? (s/n): ").strip().lower()
        if confirm != 's':
            return None
    
    print("\n🔄 Processando código...")
    
    try:
        print("   • Trocando código por token...")
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        print("   • Salvando token...")
        with open(DRIVE_TOKEN, "w") as f:
            json.dump({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }, f, indent=2)
        
        print("✅ Token obtido e salvo!\n")
        return creds
        
    except Exception as e:
        print(f"\n❌ Erro ao processar: {e}")
        print("\nDicas:")
        print("  • Copie o código COMPLETO (com '4/0Af...')")
        print("  • Não inclua 'code=' no início")
        print("  • Não inclua '&state=' no final")
        return None

def search_resumes(creds):
    """Busca currículos no Google Drive"""
    
    print("="*80)
    print("📂 BUSCANDO SEUS CURRÍCULOS".center(80))
    print("="*80 + "\n")
    
    try:
        drive = build("drive", "v3", credentials=creds)
        
        terms = ["curriculo", "currículo", "curriculum", "cv", "resume"]
        all_files = []
        
        print("🔍 Procurando por termos...")
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
                    print(f"   ✓ '{term}': {len(files)} arquivo(s)")
                    all_files.extend(files)
            except Exception as e:
                print(f"   ⚠️  '{term}': erro ({e})")
        
        if not all_files:
            print("\n❌ Nenhum currículo encontrado")
            print("\nDicas:")
            print("  • Certifique-se de ter arquivos no Google Drive")
            print("  • Os nomes devem conter: currículo, curriculum, cv ou resume")
            print("  • O arquivo não deve estar na lixeira")
            return False
        
        # Remover duplicatas e ordenar
        unique = {f["id"]: f for f in all_files}
        sorted_files = sorted(unique.values(), 
                             key=lambda f: f.get("modifiedTime", ""), 
                             reverse=True)
        
        print(f"\n✅ {len(sorted_files)} currículo(s) encontrado(s)!")
        print("\n" + "="*80)
        print("📋 SEUS CURRÍCULOS".center(80))
        print("="*80 + "\n")
        
        for i, f in enumerate(sorted_files[:5], 1):
            name = f.get("name", "Sem nome")
            size = int(f.get("size", 0)) / 1024
            modified = f.get("modifiedTime", "")
            link = f.get("webViewLink", "N/A")
            
            marker = " ⭐ MAIS RECENTE" if i == 1 else ""
            
            print(f"[{i}] {name}{marker}")
            print(f"   Tamanho: {size:.1f} KB")
            print(f"   Modificado: {modified[:10]}")
            print(f"   🔗 {link}\n")
        
        print("="*80)
        print("✅ SUCCESS!".center(80))
        print("="*80 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao buscar currículos: {e}")
        return False

def main():
    print_banner()
    
    # Gerar URL
    auth_url, flow = generate_auth_url()
    
    # Mostrar instruções
    display_instructions(auth_url)
    
    # Capturar e processar código
    creds = capture_and_process_code(flow)
    
    if not creds:
        print("\n❌ Falha na autenticação")
        return 1
    
    # Buscar currículos
    if search_resumes(creds):
        print("\n" + "🎯 "*20)
        print("\n📝 PRÓXIMAS AÇÕES:")
        print("   1. Clique nos links acima para abrir seus currículos")
        print("   2. Atualize com experiência B3 S.A. (14/03/2022 - 09/02/2026)")
        print("   3. Salve o arquivo novamente no Drive")
        print("   4. Sincronize com seu LinkedIn (se desejar)\n")
        print("🎯 "*20 + "\n")
        return 0
    else:
        return 1

if __name__ == "__main__":
    import sys
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro: {e}")
        sys.exit(1)
