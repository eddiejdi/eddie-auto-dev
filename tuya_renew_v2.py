#!/usr/bin/env python3
"""
Tuya IoT Core Renewal — 2 fases:
  Fase 1: Abre Chrome com perfil persistente. Voce faz login manualmente.
  Fase 2: Navega e renova IoT Core automaticamente (sessao ja ativa).
  
Uso:
  python tuya_renew_v2.py login    # Fase 1 - login manual
  python tuya_renew_v2.py renew    # Fase 2 - automacao pos-login
"""
import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROFILE_DIR = os.path.expanduser("~/.tuya_chrome_profile")
PROJECT_ID = "p1768171340520uw8ar4"
SS_DIR = "/home/edenilson/eddie-auto-dev/screenshots"

def get_driver():
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=opts)

def ss(driver, name):
    driver.save_screenshot(f"{SS_DIR}/{name}")
    print(f"  [ss] {name}")

def fase_login():
    """Fase 1: Abre browser para login manual."""
    print("=" * 60)
    print("  FASE 1: LOGIN MANUAL")
    print("  Faca login em platform.tuya.com no navegador que vai abrir")
    print("  Depois pressione ENTER aqui para fechar")
    print("=" * 60)
    
    driver = get_driver()
    try:
        driver.get("https://auth.tuya.com/?from=https://platform.tuya.com/cloud")
        print("\n  >>> Faca login manualmente no navegador <<<")
        print("  >>> Depois pressione ENTER aqui <<<")
        input()
        
        url = driver.current_url
        print(f"  URL final: {url}")
        
        if "platform.tuya.com" in url:
            print("  [OK] Login parece ter funcionado!")
        else:
            print("  [!] Verifique se o login foi feito corretamente")
        
        print("  Sessao salva em:", PROFILE_DIR)
    finally:
        driver.quit()
        print("  [OK] Navegador fechado. Execute: python tuya_renew_v2.py renew")

def fase_renew():
    """Fase 2: Usa sessao salva para renovar IoT Core."""
    print("=" * 60)
    print("  FASE 2: RENOVACAO IoT Core")
    print("  Usando sessao salva de login anterior")
    print("=" * 60)
    
    driver = get_driver()
    wait = WebDriverWait(driver, 15)
    
    try:
        # 1. Verificar se sessao esta ativa
        print("\n[1] Verificando sessao...")
        driver.get("https://platform.tuya.com/cloud")
        time.sleep(5)
        ss(driver, "v2_01_cloud.png")
        
        url = driver.current_url
        print(f"  URL: {url}")
        
        if "auth.tuya.com" in url:
            print("  [ERRO] Sessao expirada! Execute: python tuya_renew_v2.py login")
            return False
        
        print("  [OK] Sessao ativa!")
        
        # 2. Cloud Services
        print("\n[2] Navegando para Cloud Services...")
        driver.get("https://platform.tuya.com/cloud/services")
        time.sleep(5)
        ss(driver, "v2_02_services.png")
        
        page = driver.find_element(By.TAG_NAME, "body").text
        print(f"  IoT Core na pagina: {'IoT Core' in page or 'iot core' in page.lower()}")
        
        # Listar TODOS os botoes
        buttons = driver.find_elements(By.TAG_NAME, "button")
        links = driver.find_elements(By.TAG_NAME, "a")
        
        print(f"  Botoes totais: {len(buttons)}, Links totais: {len(links)}")
        relevant_btns = []
        for b in buttons:
            txt = b.text.strip()
            if txt and any(k in txt.lower() for k in ["trial", "free", "subscri", "enable", "renew", "buy", "detail", "view"]):
                visible = b.is_displayed()
                print(f"  [BTN] '{txt}' visible={visible}")
                if visible:
                    relevant_btns.append(b)
        
        for a in links:
            txt = a.text.strip()
            href = a.get_attribute("href") or ""
            if txt and any(k in txt.lower() for k in ["trial", "free", "subscri", "enable", "renew", "buy", "detail"]):
                visible = a.is_displayed()
                print(f"  [LINK] '{txt}' href={href[:80]} visible={visible}")
                if visible:
                    relevant_btns.append(a)
        
        # 3. Clicar Free Trial/Subscribe
        print("\n[3] Tentando ativar IoT Core...")
        clicked = False
        for btn in relevant_btns:
            txt = btn.text.strip().lower()
            if "free" in txt or "trial" in txt or "subscri" in txt:
                print(f"  Clicando: '{btn.text.strip()}'")
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                time.sleep(0.5)
                btn.click()
                clicked = True
                time.sleep(3)
                ss(driver, "v2_03_clicked.png")
                break
        
        if not clicked and relevant_btns:
            print(f"  Clicando primeiro relevante: '{relevant_btns[0].text.strip()}'")
            relevant_btns[0].click()
            clicked = True
            time.sleep(3)
            ss(driver, "v2_03_clicked.png")
        
        # 4. Confirmar modal se existir
        if clicked:
            print("\n[4] Verificando modal de confirmacao...")
            time.sleep(2)
            for sel in [
                ".ant-modal-footer button.ant-btn-primary",
                "button.ant-btn-primary",
                "//button[contains(text(),'Confirm')]",
                "//button[contains(text(),'OK')]",
                "//button[contains(text(),'Submit')]",
                "//button[contains(text(),'Authorize')]",
            ]:
                try:
                    if sel.startswith("//"):
                        el = driver.find_element(By.XPATH, sel)
                    else:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed() and el.text.strip():
                        print(f"  Modal encontrado. Clicando: '{el.text.strip()}'")
                        el.click()
                        time.sleep(3)
                        ss(driver, "v2_04_confirmed.png")
                        break
                except:
                    pass
        
        # 5. Verificar overview do projeto
        print("\n[5] Verificando overview do projeto...")
        driver.get(f"https://platform.tuya.com/cloud/basic?id={PROJECT_ID}")
        time.sleep(5)
        ss(driver, "v2_05_overview.png")
        
        page = driver.find_element(By.TAG_NAME, "body").text
        for line in page.split("\n"):
            line = line.strip()
            if any(k in line.lower() for k in ["data center", "region", "america", "eastern", "western", "iot"]):
                print(f"  {line[:120]}")
        
        # 6. Service API — autorizar projeto
        print("\n[6] Verificando Service API do projeto...")
        driver.get(f"https://platform.tuya.com/cloud/appinfo/cappId/{PROJECT_ID}")
        time.sleep(5)
        ss(driver, "v2_06_service_api.png")
        
        page = driver.find_element(By.TAG_NAME, "body").text
        for line in page.split("\n"):
            line = line.strip()
            if any(k in line.lower() for k in ["iot core", "authorization", "subscri", "expired", "active", "authorize"]):
                print(f"  {line[:120]}")
        
        # Tentar clicar Go to Authorize
        for sel in [
            "//button[contains(text(),'Authorize')]",
            "//a[contains(text(),'Authorize')]",
            "//button[contains(text(),'Subscribe')]",
        ]:
            try:
                el = driver.find_element(By.XPATH, sel)
                if el.is_displayed():
                    print(f"  Clicando: '{el.text.strip()}'")
                    el.click()
                    time.sleep(3)
                    ss(driver, "v2_07_authorize.png")
                    
                    # Se abriu pagina de subscribe, marcar IoT Core
                    page = driver.find_element(By.TAG_NAME, "body").text
                    if "iot core" in page.lower():
                        # Marcar checkbox e confirmar
                        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                        for cb in checkboxes:
                            try:
                                parent_text = cb.find_element(By.XPATH, "..").text.lower()
                                if "iot" in parent_text:
                                    if not cb.is_selected():
                                        cb.click()
                                        print(f"  IoT Core checkbox marcado")
                            except:
                                pass
                        
                        # Confirmar
                        for c_sel in ["//button[contains(text(),'Confirm')]", "//button[contains(text(),'OK')]", "button.ant-btn-primary"]:
                            try:
                                if c_sel.startswith("//"):
                                    c_el = driver.find_element(By.XPATH, c_sel)
                                else:
                                    c_el = driver.find_element(By.CSS_SELECTOR, c_sel)
                                if c_el.is_displayed():
                                    c_el.click()
                                    time.sleep(3)
                                    break
                            except:
                                pass
                    break
            except:
                pass
        
        # 7. Testar API
        print("\n[7] Testando API...")
        import tinytuya
        
        for region in ["us-e", "us"]:
            try:
                c = tinytuya.Cloud(
                    apiRegion=region,
                    apiKey=os.environ["TUYA_ACCESS_ID"],
                    apiSecret=os.environ["TUYA_ACCESS_SECRET"],
                    apiDeviceID="ebbc9f4aaf16cce3a4wj26"
                )
                devices = c.getdevices()
                if isinstance(devices, dict) and 'Error' in devices:
                    err = devices.get('Payload', devices.get('Error', ''))
                    print(f"  [{region}] {err[:100]}")
                elif isinstance(devices, list):
                    print(f"  [{region}] SUCESSO! {len(devices)} dispositivos!")
                    for d in devices[:10]:
                        name = d.get('name', '?')
                        dev_id = d.get('id', '?')
                        key = d.get('key', '?')
                        print(f"    - {name} | id={dev_id} | key={key}")
                    return True
                else:
                    print(f"  [{region}] {str(devices)[:100]}")
            except Exception as e:
                print(f"  [{region}] {e}")
        
        return False
        
    finally:
        driver.quit()
        print("\n[OK] Navegador fechado")

if __name__ == "__main__":
    os.makedirs(SS_DIR, exist_ok=True)
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if cmd == "login":
        fase_login()
    elif cmd == "renew":
        fase_renew()
    else:
        print("Uso:")
        print("  python tuya_renew_v2.py login   # Passo 1: login manual")
        print("  python tuya_renew_v2.py renew   # Passo 2: renovar IoT Core")
        print()
        print("Executando login primeiro...")
        fase_login()
