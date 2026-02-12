#!/usr/bin/env python3
"""
🤖 Agent Selenium para Autenticação OAuth Google Drive
Automatiza: abertura navegador → login → captura código
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
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

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

class SeleniumOAuthAgent:
    def __init__(self):
        self.driver = None
        self.auth_code = None
        
    def print_header(self):
        print("\n" + "="*80)
        print("🤖 AGENT SELENIUM - AUTENTICAÇÃO OAUTH AUTOMÁTICA".center(80))
        print("="*80 + "\n")
    
    def setup_driver(self):
        """Configura o driver do Selenium"""
        print("🔧 Configurando Selenium WebDriver...")
        
        # Tentar Chrome primeiro
        try:
            options = ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            # options.add_argument("--headless")  # Comentado para ver o navegador
            
            self.driver = webdriver.Chrome(options=options, timeout=30)
            print("✅ Chrome detectado e inicializado\n")
            return True
        except:
            print("⚠️  Chrome não disponível, tentando Firefox...")
            
            try:
                options = FirefoxOptions()
                # options.add_argument("--headless")
                self.driver = webdriver.Firefox(options=options, timeout=30)
                print("✅ Firefox inicializado\n")
                return True
            except:
                print("❌ Nenhum navegador disponível (Chrome/Firefox necessário)")
                return False
    
    def generate_auth_url(self):
        """Gera URL de autorização"""
        print("📋 Gerando URL de autorização...")
        
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
        
        print(f"✅ URL gerada\n")
        return auth_url, flow
    
    def monitor_redirect(self, wait_time=300):
        """Monitora redirecionamento e captura código"""
        print("⏳ Aguardando você fazer login e autorizar...")
        print("   (Você tem 5 minutos para completar a autorização)\n")
        
        start_time = time.time()
        
        while (time.time() - start_time) < wait_time:
            try:
                # Verificar URL atual
                current_url = self.driver.current_url
                
                # Verificar se contém o código
                if "code=" in current_url:
                    print(f"\n✅ Redirecionamento detectado!")
                    print(f"   URL: {current_url[:80]}...\n")
                    
                    # Extrair código
                    parsed_url = urlparse(current_url)
                    params = parse_qs(parsed_url.query)
                    
                    if "code" in params:
                        self.auth_code = params["code"][0]
                        print(f"✅ Código capturado: {self.auth_code[:15]}...{self.auth_code[-10:]}\n")
                        return True
                
                # Verificar se página de erro
                if "error=" in current_url or "error" in current_url.lower():
                    print(f"\n❌ Erro detectado na URL!")
                    print(f"   {current_url}\n")
                    return False
                
                # Pequena pausa antes de verificar novamente
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️  Erro ao monitorar: {e}")
                time.sleep(2)
        
        print("❌ Timeout! Você não completou a autorização em tempo")
        return False
    
    def authenticate(self):
        """Fluxo completo de autenticação"""
        self.print_header()
        
        # Setup
        if not self.setup_driver():
            return False
        
        # Gerar URL
        auth_url, flow = self.generate_auth_url()
        
        # Abrir navegador
        print(f"🌐 Abrindo navegador...")
        self.driver.get(auth_url)
        print("✅ Navegador aberto. Aguardando autorização...\n")
        
        # Monitorar redirecionamento
        if not self.monitor_redirect():
            self.cleanup()
            return False
        
        # Fechar navegador
        print("🔄 Processando código...")
        self.cleanup()
        
        # Trocar código por token
        print("🔑 Trocando código por token permanente...\n")
        
        try:
            flow.fetch_token(code=self.auth_code)
            creds = flow.credentials
            
            # Salvar token
            with open(DRIVE_TOKEN, "w") as f:
                json.dump({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }, f, indent=2)
            
            print("✅ Token salvo com sucesso!\n")
            return creds
            
        except Exception as e:
            print(f"❌ Erro ao processar código: {e}\n")
            return False
    
    def cleanup(self):
        """Limpa recursos"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Navegador fechado\n")
            except:
                pass
    
    def search_resumes(self, creds):
        """Busca currículos no Drive"""
        print("="*80)
        print("📂 BUSCANDO CURRÍCULOS NO GOOGLE DRIVE".center(80))
        print("="*80 + "\n")
        
        try:
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
                        print(f"✓ '{term}': {len(files)} arquivo(s)")
                        all_files.extend(files)
                except:
                    pass
            
            if not all_files:
                print("\n❌ Nenhum currículo encontrado")
                return False
            
            # Remover duplicatas
            unique = {f["id"]: f for f in all_files}
            sorted_files = sorted(unique.values(), 
                                 key=lambda f: f.get("modifiedTime", ""), 
                                 reverse=True)
            
            print(f"\n📊 Total: {len(sorted_files)} currículo(s)")
            print("="*80 + "\n")
            
            for i, f in enumerate(sorted_files[:5], 1):
                name = f.get("name", "Sem nome")
                size = int(f.get("size", 0)) / 1024
                modified = f.get("modifiedTime", "")
                link = f.get("webViewLink", "N/A")
                
                marker = " ⭐ MAIS RECENTE" if i == 1 else ""
                print(f"[{i}] {name}{marker}")
                print(f"    Tamanho: {size:.1f} KB | Modificado: {modified[:10]}")
                print(f"    🔗 {link}\n")
            
            print("="*80)
            print("✅ SUCESSO! Currículos listados acima.\n")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao buscar currículos: {e}\n")
            return False

def main():
    agent = SeleniumOAuthAgent()
    
    creds = agent.authenticate()
    
    if creds:
        agent.search_resumes(creds)
        print("\n✅ PROCESSO CONCLUÍDO!")
        print("\nPróximas ações:")
        print("  1. Clique nos links para abrir seus currículos")
        print("  2. Atualize com experiência B3 S.A. (2022-2026)")
        print("  3. Salve novamente no Drive")
        return 0
    else:
        print("\n❌ Falha na autenticação")
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
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)
