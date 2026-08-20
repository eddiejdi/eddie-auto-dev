#!/usr/bin/env python3
"""
Selenium - Attach to existing Chrome window
Conecta a uma janela do Chrome já aberta via remote debugging
"""

import subprocess
import sys
import time


def check_selenium():
    """Verifica se Selenium está instalado"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        return True
    except ImportError:
        print("❌ Selenium não instalado. Instalando...")
        subprocess.run([sys.executable, "-m", "pip", "install", "selenium", "-q"])
        return True

def start_chrome_debug_mode():
    """Inicia Chrome em modo debug (Windows)"""
    print("\n" + "="*60)
    print("🚀 INSTRUÇÕES PARA CHROME DEBUG MODE")
    print("="*60)
    print("""
Para conectar o Selenium a uma janela existente, você precisa:

1. FECHAR TODAS as janelas do Chrome primeiro

2. Abrir Chrome com debug mode (execute no PowerShell):
   
   Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=9222"

3. Depois execute este script novamente

Ou use a opção 2 abaixo para abrir automaticamente.
""")
    return False


def attach_to_chrome():
    """Conecta ao Chrome em modo debug"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    print("\n🔌 Conectando ao Chrome (porta 9222)...")
    
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=options)
        print(f"✅ Conectado! Título atual: {driver.title}")
        print(f"📍 URL: {driver.current_url}")
        return driver
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        print("\n⚠️ Certifique-se que o Chrome está rodando com --remote-debugging-port=9222")
        return None


def find_test_users_section(driver):
    """Localiza a seção de Test Users no OAuth consent screen"""
    from selenium.webdriver.common.by import By
    
    print("\n🔍 Procurando seção de Test Users...")
    
    # Navegar para a página correta se necessário
    consent_url = "https://console.cloud.google.com/apis/credentials/consent"
    if "consent" not in driver.current_url:
        print(f"📍 Navegando para: {consent_url}")
        driver.get(consent_url + "?project=homelab-483803")
        time.sleep(3)
    
    # Lista de possíveis seletores para encontrar elementos
    selectors_to_try = [
        # Botões de adicionar usuário
        ("xpath", "//button[contains(., 'Add users')]", "Botão 'Add users'"),
        ("xpath", "//button[contains(., 'Adicionar usuários')]", "Botão 'Adicionar usuários'"),
        ("xpath", "//span[contains(text(), 'Add users')]", "Span 'Add users'"),
        ("xpath", "//span[contains(text(), 'Adicionar')]", "Span 'Adicionar'"),
        
        # Links de Test users
        ("xpath", "//a[contains(., 'Test users')]", "Link 'Test users'"),
        ("xpath", "//a[contains(., 'Usuários de teste')]", "Link 'Usuários de teste'"),
        
        # Seções com headers
        ("xpath", "//*[contains(text(), 'Test users')]", "Texto 'Test users'"),
        ("xpath", "//*[contains(text(), 'Usuários de teste')]", "Texto 'Usuários de teste'"),
        
        # Campos de input para email
        ("xpath", "//input[@type='email']", "Input de email"),
        ("xpath", "//input[contains(@placeholder, 'email')]", "Input com placeholder email"),
        ("xpath", "//input[contains(@aria-label, 'email')]", "Input com aria-label email"),
        
        # Material Design buttons
        ("css", "button[aria-label*='Add']", "Botão Material Add"),
        ("css", "button.mdc-button", "Botões MDC"),
        ("css", "[data-test-id*='add']", "Data-test add"),
        
        # Tabela de usuários
        ("xpath", "//table//th[contains(., 'User')]", "Tabela de usuários"),
    ]
    
    found_elements = []
    
    for selector_type, selector, description in selectors_to_try:
        try:
            if selector_type == "xpath":
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            if elements:
                print(f"  ✅ Encontrado: {description} ({len(elements)} elemento(s))")
                for i, elem in enumerate(elements[:3]):  # Mostra até 3
                    try:
                        text = elem.text[:50] if elem.text else "(sem texto)"
                        tag = elem.tag_name
                        print(f"      [{i+1}] <{tag}> {text}")
                        found_elements.append((description, elem))
                    except:
                        pass
        except Exception:
            pass
    
    return found_elements


def analyze_page(driver):
    """Analisa a estrutura da página atual"""
    from selenium.webdriver.common.by import By
    
    print("\n📊 ANÁLISE DA PÁGINA")
    print("="*60)
    print(f"Título: {driver.title}")
    print(f"URL: {driver.current_url}")
    
    # Encontrar todos os botões
    print("\n🔘 BOTÕES NA PÁGINA:")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for i, btn in enumerate(buttons[:20]):
        try:
            text = btn.text.strip()[:40] if btn.text else ""
            aria = btn.get_attribute("aria-label") or ""
            if text or aria:
                print(f"  [{i+1}] {text} | aria: {aria}")
        except:
            pass
    
    # Encontrar todos os links
    print("\n🔗 LINKS NA PÁGINA:")
    links = driver.find_elements(By.TAG_NAME, "a")
    for i, link in enumerate(links[:20]):
        try:
            text = link.text.strip()[:40] if link.text else ""
            href = link.get_attribute("href") or ""
            if text and ("user" in text.lower() or "test" in text.lower() or "add" in text.lower()):
                print(f"  [{i+1}] {text}")
        except:
            pass
    
    # Encontrar inputs
    print("\n📝 CAMPOS DE INPUT:")
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for i, inp in enumerate(inputs[:10]):
        try:
            input_type = inp.get_attribute("type") or "text"
            placeholder = inp.get_attribute("placeholder") or ""
            aria = inp.get_attribute("aria-label") or ""
            print(f"  [{i+1}] type={input_type} | placeholder={placeholder} | aria={aria}")
        except:
            pass


def click_add_users(driver):
    """Tenta clicar no botão de adicionar usuários"""
    from selenium.webdriver.common.by import By
    
    print("\n🖱️ Tentando clicar em 'Add users'...")
    
    # Scroll para o final da página primeiro
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    
    # Tentar encontrar e clicar
    add_selectors = [
        "//button[contains(., 'Add users')]",
        "//button[contains(., 'ADD USERS')]",
        "//span[contains(text(), 'Add users')]/ancestor::button",
        "//mat-icon[contains(text(), 'add')]/ancestor::button",
        "//*[@data-test-id='add-test-users-button']",
    ]
    
    for selector in add_selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for elem in elements:
                if elem.is_displayed():
                    print(f"  ✅ Encontrado elemento clicável: {elem.text}")
                    # Scroll até o elemento
                    driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                    time.sleep(0.5)
                    elem.click()
                    print("  ✅ Clicado!")
                    time.sleep(1)
                    return True
        except Exception:
            continue
    
    print("  ❌ Não foi possível encontrar botão de adicionar")
    return False


def add_test_user(driver, email="edenilson.teixeira@rpa4all.com"):
    """Adiciona um email como test user"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    
    print(f"\n📧 Adicionando test user: {email}")
    
    # Procurar campo de input para email
    input_selectors = [
        "//input[@type='email']",
        "//input[contains(@placeholder, 'email')]",
        "//input[contains(@placeholder, 'Email')]",
        "//input[contains(@aria-label, 'email')]",
        "//textarea[contains(@placeholder, 'email')]",
    ]
    
    for selector in input_selectors:
        try:
            inputs = driver.find_elements(By.XPATH, selector)
            for inp in inputs:
                if inp.is_displayed():
                    print("  ✅ Campo de email encontrado!")
                    inp.clear()
                    inp.send_keys(email)
                    print(f"  ✅ Email digitado: {email}")
                    time.sleep(0.5)
                    
                    # Tentar confirmar
                    inp.send_keys(Keys.ENTER)
                    return True
        except Exception:
            continue
    
    print("  ❌ Campo de email não encontrado")
    return False


def interactive_mode(driver):
    """Modo interativo para explorar a página"""
    print("\n" + "="*60)
    print("🎮 MODO INTERATIVO")
    print("="*60)
    print("""
Comandos disponíveis:
  1 - Analisar página atual
  2 - Procurar seção Test Users
  3 - Clicar em 'Add users'
  4 - Adicionar email como test user
  5 - Navegar para OAuth consent
  6 - Scroll para baixo
  7 - Tirar screenshot
  8 - Executar JavaScript customizado
  0 - Sair
""")
    
    while True:
        try:
            cmd = input("\n> Comando: ").strip()
            
            if cmd == "0":
                print("👋 Saindo...")
                break
            elif cmd == "1":
                analyze_page(driver)
            elif cmd == "2":
                find_test_users_section(driver)
            elif cmd == "3":
                click_add_users(driver)
            elif cmd == "4":
                email = input("  Email [edenilson.teixeira@rpa4all.com]: ").strip()
                if not email:
                    email = "edenilson.teixeira@rpa4all.com"
                add_test_user(driver, email)
            elif cmd == "5":
                url = "https://console.cloud.google.com/apis/credentials/consent?project=homelab-483803"
                print(f"📍 Navegando para: {url}")
                driver.get(url)
                time.sleep(3)
            elif cmd == "6":
                driver.execute_script("window.scrollBy(0, 500);")
                print("  ⬇️ Scrolled 500px")
            elif cmd == "7":
                filename = f"/home/homelab/myClaude/screenshot_{int(time.time())}.png"
                driver.save_screenshot(filename)
                print(f"  📸 Screenshot salvo: {filename}")
            elif cmd == "8":
                js = input("  JavaScript: ").strip()
                if js:
                    result = driver.execute_script(js)
                    print(f"  Resultado: {result}")
            else:
                print("  ❓ Comando não reconhecido")
                
        except KeyboardInterrupt:
            print("\n👋 Interrompido")
            break
        except Exception as e:
            print(f"  ❌ Erro: {e}")


def main():
    print("="*60)
    print("🔧 SELENIUM - ATTACH TO CHROME")
    print("="*60)
    
    # Verificar selenium
    if not check_selenium():
        return
    
    print("""
Opções:
  1 - Conectar ao Chrome (deve estar rodando com --remote-debugging-port=9222)
  2 - Ver instruções para iniciar Chrome em debug mode
""")
    
    choice = input("Escolha [1]: ").strip() or "1"
    
    if choice == "2":
        start_chrome_debug_mode()
        return
    
    # Tentar conectar
    driver = attach_to_chrome()
    
    if driver:
        # Entrar em modo interativo
        interactive_mode(driver)
        print("\n✅ Sessão encerrada (navegador permanece aberto)")
    else:
        print("\n" + "="*60)
        print("⚠️ COMO INICIAR CHROME EM DEBUG MODE:")
        print("="*60)
        print("""
No PowerShell do Windows, execute:

1. Feche TODAS as janelas do Chrome

2. Execute:
   Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=9222","https://console.cloud.google.com/apis/credentials/consent?project=homelab-483803"

3. Faça login no Google se necessário

4. Execute este script novamente
""")


if __name__ == "__main__":
    main()
