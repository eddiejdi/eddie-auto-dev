#!/usr/bin/env python3
"""
🤖 AGENTE SELENIUM - Autenticação Google OAuth Automática
Automatiza: abrir URL → login → autorização → captura de código → busca de currículos
"""

import json
import re
import subprocess
import time
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Configurações
GOOGLE_EMAIL = None  # Será detectado ou solicitado
GOOGLE_PASSWORD = None  # Será detectado ou solicitado
OAUTH_URL = None  # Será passado como argumento
CREDS_FILE = Path("/home/homelab/myClaude/credentials.json")
DRIVE_DIR = Path("/home/homelab/myClaude/drive_data")
DRIVE_TOKEN = DRIVE_DIR / "token.json"

def load_or_prompt_credentials():
    """Carregar credenciais Google do arquivo ou solicitar ao usuário"""
    global GOOGLE_EMAIL, GOOGLE_PASSWORD
    
    # Tentar carregar do agent secrets
    secret_file = Path.home() / ".google_credentials.json"
    if secret_file.exists():
        try:
            with open(secret_file) as f:
                data = json.load(f)
                GOOGLE_EMAIL = data.get("email")
                GOOGLE_PASSWORD = data.get("password")
                if GOOGLE_EMAIL and GOOGLE_PASSWORD:
                    print(f"✅ Credenciais carregadas: {GOOGLE_EMAIL}")
                    return True
        except:
            pass
    
    print("""
📋 CREDENCIAIS GOOGLE (OPCIONAL)
  
Para automação completa com login automático, forneça suas credenciais.
(Deixe em branco para fazer login manualmente no navegador)

""")
    
    email = input("📧 Email Google (ou Enter para pular): ").strip()
    if not email:
        print("   ✓ Será necessário fazer login manualmente no navegador")
        return True
    
    password = input("🔐 Senha Google: ").strip()
    
    if email and password:
        GOOGLE_EMAIL = email
        GOOGLE_PASSWORD = password
        
        # Oferecer salvar
        save = input("\n💾 Salvar credenciais locais? (s/n): ").strip().lower()
        if save == 's':
            secret_file.parent.mkdir(exist_ok=True)
            with open(secret_file, 'w') as f:
                json.dump({"email": email, "password": password}, f)
            secret_file.chmod(0o600)
            print(f"✅ Salvo em {secret_file}\n")
    
    return True

def setup_selenium_driver():
    """Configurar e retornar driver Selenium"""
    options = Options()
    # Não usar headless para ver progresso
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    
    return driver

def automate_oauth_flow(driver, url):
    """Automatizar fluxo OAuth completo"""
    print("\n🤖 INICIANDO AUTOMAÇÃO SELENIUM")
    print("=" * 70)
    
    # Abrir URL
    print("\n📍 Abrindo URL de autorização...")
    driver.get(url)
    time.sleep(3)
    
    # Etapa 1: Fazer login (se credenciais fornecidas)
    if GOOGLE_EMAIL and GOOGLE_PASSWORD:
        print("📧 Etapa 1: Autenticação Google...")
        try:
            # Procurar campo de email
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            print("  ✓ Campo de email encontrado")
            
            # Inserir email
            email_field.send_keys(GOOGLE_EMAIL)
            time.sleep(1)
            
            # Clicar em Next
            next_button = driver.find_element(By.ID, "identifierNext")
            next_button.click()
            print("  ✓ Email enviado")
            
            time.sleep(2)
            
            # Inserir senha
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_field.send_keys(GOOGLE_PASSWORD)
            print("  ✓ Campo de senha encontrado")
            
            time.sleep(1)
            
            # Clicar em Next (senha)
            next_button = driver.find_element(By.ID, "passwordNext")
            next_button.click()
            print("  ✓ Senha enviada")
            
            time.sleep(4)
            
        except Exception as e:
            print(f"  ⚠️  Login automático failed: {e}")
            print("  💡 Faça login manualmente no navegador...")
    else:
        print("📧 Etapa 1: Aguardando login manual no navegador...")
        print("   💡 Faça login com sua conta Google...")
        print("   ⏳ Esperando por 60 segundos...")
        time.sleep(5)  # Aguardar usuário fazer login
    
    # Etapa 2: Aguardar e clicar em "Permitir"
    print("\n✋ Etapa 2: Procurando botão de autorização...")
    try:
        # Esperar por possível página de permissões
        time.sleep(2)
        
        # Procurar botão "Permitir" (pode ter variações)
        allow_buttons = [
            (By.XPATH, "//span[contains(text(), 'Permitir')]"),
            (By.XPATH, "//span[contains(text(), 'Allow')]"),
            (By.XPATH, "//button[contains(., 'Permitir')]"),
            (By.XPATH, "//button[contains(., 'Allow')]"),
            (By.ID, "submit_approve_access"),
            (By.XPATH, "//button[@type='button' and contains(., 'Permitir')]"),
            (By.XPATH, "//button[@type='button' and contains(., 'Allow')]"),
        ]
        
        button_found = False
        for locator in allow_buttons:
            try:
                button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(locator)
                )
                print("  ✓ Botão de autorização encontrado")
                button.click()
                button_found = True
                print("  ✓ Clicado em 'Permitir'")
                time.sleep(3)
                break
            except:
                continue
        
        if not button_found:
            print("  ℹ️  Botão não encontrado - procurando alternativas...")
            try:
                # Tentar encontrar qualquer botão que faça sentido
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    text = btn.text.lower()
                    if any(word in text for word in ["permitir", "allow", "autorizar", "authorize"]):
                        print(f"  ✓ Botão encontrado: {btn.text}")
                        btn.click()
                        button_found = True
                        print("  ✓ Clicado!")
                        time.sleep(3)
                        break
            except:
                pass
            
            if not button_found:
                print("  💡 Clique em 'Permitir' no navegador manualmente...")
                input("  Pressione ENTER após clicar: ")
    
    except Exception as e:
        print(f"  ⚠️  Erro ao clicar: {e}")
        print("  💡 Clique manualmente no botão 'Permitir'...")
        input("  Pressione ENTER após clicar: ")
    
    # Etapa 3: Capturar código da URL de redirecionamento
    print("\n🔗 Etapa 3: Capturando código de redirecionamento...")
    
    code = None
    for attempt in range(60):  # 60 tentativas de 1 segundo = 60 segundos
        try:
            current_url = driver.current_url
            
            if "code=" in current_url:
                # Extrair código
                match = re.search(r'code=([^&]+)', current_url)
                if match:
                    code = match.group(1)
                    print("  ✓ Código capturado!")
                    print(f"  📝 Código: {code[:20]}...{code[-10:]}")
                    break
            
            if "error=" in current_url:
                error_match = re.search(r'error=([^&]+)', current_url)
                if error_match:
                    error = error_match.group(1)
                    print(f"  ❌ Erro do Google: {error}")
                    break
            
            if attempt % 10 == 0 and attempt > 0:
                print(f"  ⏳ Aguardando... ({attempt}s)")
            
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Erro ao capturar: {e}")
            time.sleep(1)
    
    driver.quit()
    
    return code

def exchange_code_for_token(code):
    """Trocar código por token permanente"""
    print("\n🔄 Etapa 4: Trocando código por token...")
    
    try:
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
        
        # Fazer o fetch do token com o código
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Salvar token
        DRIVE_DIR.mkdir(exist_ok=True)
        with open(DRIVE_TOKEN, "w") as f:
            json.dump({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }, f, indent=2)
        
        print("  ✅ Token salvo com sucesso!")
        return creds
        
    except Exception as e:
        print(f"  ❌ Erro ao trocar código: {e}")
        return None

def search_resumes(creds):
    """Buscar currículos no Google Drive"""
    print("\n📂 Etapa 5: Buscando currículos no Drive...")
    
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
                    print(f"  ✓ '{term}': {len(files)} arquivo(s)")
                    all_files.extend(files)
            except:
                pass
        
        if not all_files:
            print("  ⚠️  Nenhum currículo encontrado")
            return False
        
        # Remover duplicatas
        unique = {f["id"]: f for f in all_files}
        sorted_files = sorted(unique.values(), 
                             key=lambda f: f.get("modifiedTime", ""), 
                             reverse=True)
        
        print(f"\n  📊 Total de currículos: {len(sorted_files)}")
        print(f"  {'=' * 78}")
        
        for i, f in enumerate(sorted_files[:5], 1):
            name = f.get("name", "Sem nome")
            size = int(f.get("size", 0)) / 1024
            modified = f.get("modifiedTime", "")
            link = f.get("webViewLink", "N/A")
            
            marker = " ⭐ MAIS RECENTE" if i == 1 else ""
            print(f"\n  [{i}] {name}{marker}")
            print(f"      Tamanho: {size:.1f} KB | Modificado: {modified[:10]}")
            print(f"      🔗 {link}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro ao buscar currículos: {e}")
        return False

def main():
    import sys
    
    print("\n" + "🤖" * 30)
    print("\n  AGENTE SELENIUM - AUTENTICAÇÃO GOOGLE AUTOMÁTICA\n")
    print("🤖" * 30)
    
    # URL de autorização
    global OAUTH_URL
    if len(sys.argv) > 1:
        OAUTH_URL = sys.argv[1]
    else:
        print("\n❌ Uso: python3 script.py <OAUTH_URL>")
        print("\nExemplo:")
        print('  python3 script.py "https://accounts.google.com/o/oauth2/auth?..."')
        sys.exit(1)
    
    # Carregar credenciais
    if not load_or_prompt_credentials():
        print("❌ Credenciais não fornecidas")
        sys.exit(1)
    
    # Configurar Selenium
    driver = setup_selenium_driver()
    
    try:
        # Executar fluxo OAuth automático
        code = automate_oauth_flow(driver, OAUTH_URL)
        
        if not code:
            print("\n❌ Código não capturado")
            sys.exit(1)
        
        # Trocar código por token
        creds = exchange_code_for_token(code)
        if not creds:
            print("\n❌ Token não obtido")
            sys.exit(1)
        
        # Buscar currículos
        # Copiar token para servidor
        print("\n📤 Copiando token para servidor remoto...")
        try:
            subprocess.run([
                "scp",
                str(DRIVE_TOKEN),
                "homelab@192.168.15.2:/home/homelab/myClaude/drive_data/"
            ], check=True, capture_output=True)
            print("  ✅ Token copiado para servidor")
        except Exception as e:
            print(f"  ⚠️  Erro ao copiar token: {e}")
        
        if search_resumes(creds):
            print("\n" + "=" * 78)
            print("✅ SUCESSO! Acesse os links acima para abrir seus currículos.")
            print("=" * 78 + "\n")
            sys.exit(0)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
