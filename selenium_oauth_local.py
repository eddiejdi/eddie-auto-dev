#!/usr/bin/env python3
"""
🤖 Agent Selenium Local - Executa no seu computador
Abre o navegador LOCAL e captura o código automaticamente
"""

import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import InstalledAppFlow
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels"
]

class LocalSeleniumAgent:
    def __init__(self):
        self.driver = None
        self.auth_code = None
        
    def print_header(self):
        print("\n" + "="*80)
        print("🤖 AGENT SELENIUM LOCAL - AUTENTICAÇÃO OAUTH".center(80))
        print("="*80 + "\n")
    
    def setup_driver(self):
        """Configura o driver do Selenium"""
        print("🔧 Configurando Selenium (Chrome/Firefox)...\n")
        
        # Tentar Chrome primeiro
        try:
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            options = ChromeOptions()
            self.driver = webdriver.Chrome(options=options, timeout=30)
            print("✅ Chrome inicializado\n")
            return True
        except:
            print("⚠️  Chrome não disponível, tentando Firefox...")
            
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                options = FirefoxOptions()
                self.driver = webdriver.Firefox(options=options, timeout=30)
                print("✅ Firefox inicializado\n")
                return True
            except:
                print("❌ Nenhum navegador disponível (Chrome/Firefox necessário)")
                return False
    
    def authenticate_and_search(self):
        """Fluxo completo: autorizar no Google e buscar currículos"""
        
        # Preparar para chamar o script remoto com SSH
        import subprocess
        
        print("🔄 Preparando autenticação remota...")
        print("   O navegador será aberto em seu computador\n")
        
        # Gerar URL de autorização via SSH
        cmd = """ssh homelab@192.168.15.2 'python3 << ENDPYTHON
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

CREDS_FILE = Path("/home/homelab/myClaude/credentials.json")
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels"
]

flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
print(auth_url)
ENDPYTHON
'"""
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        auth_url = result.stdout.strip()
        
        if not auth_url or not auth_url.startswith("https://"):
            print("❌ Erro ao gerar URL de autorização")
            return False
        
        print(f"🔗 URL de autorização gerada\n")
        
        # Setup driver local
        if not self.setup_driver():
            return False
        
        # Abrir navegador
        print(f"🌐 Abrindo navegador com autorização...")
        self.driver.get(auth_url)
        print("✅ Navegador aberto. Aguarde pela página de Google...\n")
        
        # Monitorar redirecionamento
        print("⏳ Aguardando você autorizar... (5 minutos)")
        print("   1. Faça login com sua conta Google")
        print("   2. Clique em 'Permitir'\n")
        
        start_time = time.time()
        timeout = 300
        
        while (time.time() - start_time) < timeout:
            try:
                current_url = self.driver.current_url
                
                if "code=" in current_url:
                    print(f"\n✅ REDIRECIONAMENTO DETECTADO!")
                    print(f"   Capturando código...\n")
                    
                    # Extrair código
                    parsed_url = urlparse(current_url)
                    params = parse_qs(parsed_url.query)
                    
                    if "code" in params:
                        self.auth_code = params["code"][0]
                        print(f"✅ Código capturado com sucesso!")
                        print(f"   {self.auth_code[:20]}...{self.auth_code[-10:]}\n")
                        
                        # Fechar navegador
                        self.driver.quit()
                        print("✅ Navegador fechado\n")
                        
                        # Usar código para autenticar e buscar currículos
                        return self.complete_auth_and_search()
                
                if "error=" in current_url:
                    print(f"\n❌ Erro no Google OAuth")
                    print(f"   {current_url}\n")
                    self.driver.quit()
                    return False
                
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️  {e}")
                time.sleep(2)
        
        print("❌ Timeout! Você não completou a autorização")
        self.driver.quit()
        return False
    
    def complete_auth_and_search(self):
        """Completa autenticação e busca currículos"""
        
        import subprocess
        import json
        
        # Enviar código para servidor e processar
        # O código já foi armazenado em self.auth_code
        
        cmd = f"""ssh homelab@192.168.15.2 'python3 << ENDPYTHON
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

print("🔄 Processando autorização...")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)

try:
    flow.fetch_token(code="{self.auth_code}")
    creds = flow.credentials
    
    # Salvar token
    with open(DRIVE_TOKEN, "w") as f:
        json.dump({{
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }}, f, indent=2)
    
    print("✅ Token salvo!")
    
    # Buscar currículos
    print("\\n📂 Buscando currículos...")
    
    drive = build("drive", "v3", credentials=creds)
    
    terms = ["curriculo", "currículo", "curriculum", "cv", "resume"]
    all_files = []
    
    for term in terms:
        q = f"name contains '{{term}}' and trashed=false"
        try:
            results = drive.files().list(
                q=q,
                pageSize=10,
                orderBy="modifiedTime desc",
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)"
            ).execute()
            
            files = results.get("files", [])
            if files:
                print(f"✓ '{{term}}': {{len(files)}} arquivo(s)")
                all_files.extend(files)
        except:
            pass
    
    if not all_files:
        print("\\n❌ Nenhum currículo encontrado")
        exit(1)
    
    # Remover duplicatas
    unique = {{f["id"]: f for f in all_files}}
    sorted_files = sorted(unique.values(), 
                         key=lambda f: f.get("modifiedTime", ""), 
                         reverse=True)
    
    print(f"\\n📊 {{len(sorted_files)}} currículo(s) encontrado(s):")
    print("="*70 + "\\n")
    
    for i, f in enumerate(sorted_files[:5], 1):
        name = f.get("name", "Sem nome")
        size = int(f.get("size", 0)) / 1024
        modified = f.get("modifiedTime", "")
        link = f.get("webViewLink", "N/A")
        
        marker = " ⭐ MAIS RECENTE" if i == 1 else ""
        print(f"[{{i}}] {{name}}{{marker}}")
        print(f"    Tamanho: {{size:.1f}} KB | Modificado: {{modified[:10]}}")
        print(f"    🔗 {{link}}\\n")
    
    print("="*70)
    print("✅ Sucesso!")
    
except Exception as e:
    print(f"❌ Erro: {{e}}")
    exit(1)
ENDPYTHON
'"""
        
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0

def main():
    agent = LocalSeleniumAgent()
    agent.print_header()
    
    print("""
📌 COMO FUNCIONA:

1. Um navegador será aberto em seu computador
2. Você fará login com sua conta Google (como usual)
3. Você clica em "Permitir"
4. O código será capturado automaticamente
5. Seus currículos serão listados

⏱️  Tempo: ~3-5 minutos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

""")
    
    if agent.authenticate_and_search():
        print("\n" + "="*80)
        print("✅ PROCESSO CONCLUÍDO COM SUCESSO!".center(80))
        print("="*80)
        print("\nProximas ações:")
        print("  1. Clique nos links para abrir seus currículos")
        print("  2. Atualize com experiência B3 S.A. recente")
        print("  3. Salve novamente no Drive\n")
        return 0
    else:
        print("\n❌ Falha no processo")
        return 1

if __name__ == "__main__":
    import sys
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
