#!/usr/bin/env python3
"""
Renova IoT Core Free Trial no data center Eastern America.
Navega direto para a pagina do projeto e verifica os servicos.
"""
import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

EMAIL = os.environ.get("TUYA_EMAIL", "edenilson.adm@gmail.com")
PASSWORD = os.environ["TUYA_PASSWORD"]  # Required env var
PROJECT_ID = "p1768171340520uw8ar4"

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--start-maximized")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])

driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 20)

def ss(name):
    driver.save_screenshot(f"/home/edenilson/eddie-auto-dev/screenshots/{name}")
    print(f"  [ss] {name}")

try:
    # 1. Login
    print("[1] Login...")
    driver.get("https://auth.tuya.com/?from=https://platform.tuya.com/cloud")
    time.sleep(3)
    ss("renew_01_login.png")
    
    # Preencher email
    email_filled = False
    for sel in [
        "input[placeholder*='email' i]",
        "input[placeholder*='mail' i]",
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='account' i]",
    ]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.clear()
            el.send_keys(EMAIL)
            email_filled = True
            print(f"  Email via: {sel}")
            break
        except:
            pass
    
    if not email_filled:
        # Tentar todos os inputs
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            t = inp.get_attribute("type") or ""
            p = inp.get_attribute("placeholder") or ""
            if t in ("text", "email", "") and "pass" not in p.lower():
                inp.clear()
                inp.send_keys(EMAIL)
                email_filled = True
                print(f"  Email via input generico (type={t})")
                break
    
    # Preencher senha
    time.sleep(0.5)
    pwd_filled = False
    for sel in ["input[type='password']", "input[name='password']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.clear()
            el.send_keys(PASSWORD)
            pwd_filled = True
            print(f"  Senha via: {sel}")
            break
        except:
            pass
    
    ss("renew_02_credentials.png")
    
    # Clicar login
    time.sleep(0.5)
    for sel in [
        "button[type='submit']",
        "button.login-btn",
        "//button[contains(text(),'Log')]",
        "//button[contains(text(),'log')]",
        "//button[contains(text(),'Sign')]",
    ]:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            el.click()
            print(f"  Login click: {sel}")
            break
        except:
            pass
    
    time.sleep(5)
    ss("renew_03_after_login.png")
    
    # Verificar se precisa resolver CAPTCHA
    url = driver.current_url
    if "auth.tuya.com" in url:
        print("  [!] Ainda na pagina de auth - CAPTCHA pode ser necessario")
        print("  >>> Resolva manualmente e pressione ENTER <<<")
        input()
        time.sleep(2)
    
    # 2. Navegar direto para Cloud Services do projeto
    print("\n[2] Navegando para Cloud Services...")
    # Tentar acessar direto a pagina de servicos
    cloud_url = f"https://platform.tuya.com/cloud/services?id={PROJECT_ID}"
    driver.get(cloud_url)
    time.sleep(5)
    ss("renew_04_cloud_services.png")
    
    # 3. Procurar IoT Core e verificar status
    print("\n[3] Procurando IoT Core...")
    page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    
    if "iot core" in page_text:
        print("  IoT Core encontrado na pagina")
    else:
        print("  IoT Core NAO encontrado, tentando outra URL...")
        driver.get("https://platform.tuya.com/cloud/services")
        time.sleep(5)
        ss("renew_04b_cloud_services_alt.png")
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    
    # Buscar todos os botoes/links relacionados a trial/subscribe
    print("\n[4] Procurando botoes de Subscribe/Trial...")
    all_elements = driver.find_elements(By.XPATH, "//*")
    
    # Listar todos os botoes visiveis
    buttons = driver.find_elements(By.TAG_NAME, "button")
    links = driver.find_elements(By.TAG_NAME, "a")
    
    print(f"  Total de botoes: {len(buttons)}")
    print(f"  Total de links: {len(links)}")
    
    for btn in buttons:
        txt = btn.text.strip()
        if txt and any(k in txt.lower() for k in ["trial", "subscribe", "free", "enable", "activate", "renew", "buy"]):
            print(f"  [BTN] '{txt}' visible={btn.is_displayed()}")
    
    for lnk in links:
        txt = lnk.text.strip()
        href = lnk.get_attribute("href") or ""
        if txt and any(k in txt.lower() for k in ["trial", "subscribe", "free", "enable", "activate", "renew", "buy"]):
            print(f"  [LINK] '{txt}' href={href[:80]}")
    
    # 5. Tentar clicar em Free Trial / Subscribe
    print("\n[5] Tentando ativar IoT Core...")
    clicked = False
    for attempt_sel in [
        "//button[contains(text(),'Free Trial')]",
        "//a[contains(text(),'Free Trial')]",
        "//button[contains(text(),'Subscribe')]",
        "//a[contains(text(),'Subscribe')]",
        "//button[contains(text(),'Try')]",
        "//button[contains(text(),'Enable')]",
        "//button[contains(text(),'Activate')]",
        "//button[contains(text(),'Renew')]",
        "//span[contains(text(),'Free Trial')]",
        "//span[contains(text(),'Subscribe')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, attempt_sel)
            if el.is_displayed():
                print(f"  Clicando: {attempt_sel}")
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                time.sleep(0.5)
                el.click()
                clicked = True
                time.sleep(3)
                ss("renew_05_clicked.png")
                break
        except:
            pass
    
    if not clicked:
        print("  Nenhum botao de trial/subscribe encontrado")
    
    # 6. Verificar se tem dialog de confirmacao
    time.sleep(2)
    page_text = driver.find_element(By.TAG_NAME, "body").text
    if "confirm" in page_text.lower() or "ok" in page_text.lower():
        for sel in [
            "//button[contains(text(),'Confirm')]",
            "//button[contains(text(),'OK')]",
            "//button[contains(text(),'Submit')]",
            "//button[contains(@class,'confirm')]",
            ".ant-modal-footer button.ant-btn-primary",
            "button.ant-btn-primary",
        ]:
            try:
                if sel.startswith("//") or sel.startswith("."):
                    if sel.startswith("//"):
                        el = driver.find_element(By.XPATH, sel)
                    else:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                else:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    print(f"  Confirmando: {sel}")
                    el.click()
                    time.sleep(3)
                    ss("renew_06_confirmed.png")
                    break
            except:
                pass
    
    # 7. Navegar para a pagina do projeto overview para verificar data center
    print("\n[7] Verificando Overview do projeto...")
    overview_url = f"https://platform.tuya.com/cloud/basic?id={PROJECT_ID}"
    driver.get(overview_url)
    time.sleep(5)
    ss("renew_07_overview.png")
    
    # Mostrar informacoes do projeto
    page_text = driver.find_element(By.TAG_NAME, "body").text
    # Procurar data center info
    for line in page_text.split("\n"):
        line = line.strip()
        if any(k in line.lower() for k in ["data center", "region", "america", "eastern", "western", "project"]):
            print(f"  INFO: {line[:120]}")
    
    # 8. Agora navegar para Service API tab
    print("\n[8] Navegando para Service API...")
    api_url = f"https://platform.tuya.com/cloud/appinfo/cappId/{PROJECT_ID}"
    driver.get(api_url)
    time.sleep(5)
    ss("renew_08_service_api.png")
    
    # Verificar APIs subscritas
    page_text = driver.find_element(By.TAG_NAME, "body").text
    for line in page_text.split("\n"):
        line = line.strip()
        if any(k in line.lower() for k in ["iot core", "authorization", "api", "subscri", "expired", "active"]):
            print(f"  API: {line[:120]}")
    
    # 9. Testar API diretamente
    print("\n[9] Testando API apos renovacao...")
    import tinytuya
    for region in ["us", "us-e"]:
        try:
            c = tinytuya.Cloud(
                apiRegion=region,
                apiKey=os.environ["TUYA_ACCESS_ID"],
                apiSecret=os.environ["TUYA_ACCESS_SECRET"],
                apiDeviceID="ebbc9f4aaf16cce3a4wj26"
            )
            devices = c.getdevices()
            if isinstance(devices, dict) and 'Error' in devices:
                print(f"  [{region}] Error: {devices.get('Payload', devices.get('Error', ''))[:100]}")
            elif isinstance(devices, list):
                print(f"  [{region}] OK! {len(devices)} dispositivos")
                for d in devices[:5]:
                    print(f"    - {d.get('name','?')} | id={d.get('id','?')} | key={d.get('key','?')}")
            else:
                print(f"  [{region}] {str(devices)[:100]}")
        except Exception as e:
            print(f"  [{region}] Exception: {e}")

    print("\n[OK] Processo concluido!")
    input("Pressione ENTER para fechar")

except Exception as e:
    print(f"\n[ERRO] {e}")
    import traceback
    traceback.print_exc()
    ss("renew_error.png")
    input("Pressione ENTER para fechar")

finally:
    try:
        driver.quit()
        print("[OK] Chrome fechado")
    except:
        pass
