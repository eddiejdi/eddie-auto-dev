#!/usr/bin/env python3
"""
Renova IoT Core Free Trial no Tuya Platform usando undetected-chromedriver.
Foco: regiao Eastern America (us-e) - a regiao correta do projeto.
"""
import time
import sys
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie_88_tp!"
PROJECT_ID = "p1768171340520uw8ar4"

print("=" * 60)
print("  TUYA IoT Core Renewal - undetected-chromedriver")
print("  Regiao alvo: Eastern America (us-e)")
print("=" * 60)

# Usar undetected_chromedriver para evitar deteccao
driver = uc.Chrome(headless=False, use_subprocess=True, version_main=144)
wait = WebDriverWait(driver, 15)

def ss(name):
    path = f"/home/edenilson/eddie-auto-dev/screenshots/{name}"
    driver.save_screenshot(path)
    print(f"  [ss] {name}")

try:
    # 1. Login
    print("\n[1] Login em platform.tuya.com...")
    driver.get("https://auth.tuya.com/?from=https://platform.tuya.com/cloud")
    time.sleep(4)
    ss("uc_01_login.png")
    
    # Preencher email
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
            print(f"  Email: OK ({sel})")
            break
        except:
            pass
    
    time.sleep(0.5)
    
    # Preencher senha
    for sel in ["input[type='password']", "input[name='password']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.clear()
            el.send_keys(PASSWORD)
            print(f"  Senha: OK ({sel})")
            break
        except:
            pass
    
    ss("uc_02_creds.png")
    time.sleep(0.5)
    
    # Clicar login
    for sel in [
        "button[type='submit']",
        "//button[contains(text(),'Log')]",
        "//button[contains(text(),'Sign')]",
    ]:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            el.click()
            print(f"  Login click: OK")
            break
        except:
            pass
    
    time.sleep(6)
    ss("uc_03_after_login.png")
    
    url = driver.current_url
    print(f"  URL: {url}")
    
    if "auth.tuya.com" in url:
        print("\n  [!] Login pode ter falhado (CAPTCHA?)")
        print("  >>> Se necessario, resolva manualmente e pressione ENTER <<<")
        input()
        time.sleep(2)
    
    print("  Login OK!")
    
    # 2. Ir para Cloud Services
    print("\n[2] Navegando para Cloud Services...")
    driver.get("https://platform.tuya.com/cloud/services")
    time.sleep(5)
    ss("uc_04_cloud_services.png")
    
    page = driver.find_element(By.TAG_NAME, "body").text.lower()
    print(f"  IoT Core na pagina: {'iot core' in page}")
    
    # 3. Procurar e clicar IoT Core -> Free Trial / Subscribe
    print("\n[3] Procurando IoT Core...")
    
    # Listar servicos encontrados
    cards = driver.find_elements(By.CSS_SELECTOR, "[class*='card'], [class*='Card'], [class*='service'], [class*='Service']")
    print(f"  Cards encontrados: {len(cards)}")
    
    # Procurar botoes de trial
    found_buttons = []
    for btn_text in ["Free Trial", "Subscribe", "Try", "Enable", "Renew"]:
        btns = driver.find_elements(By.XPATH, f"//button[contains(text(),'{btn_text}')] | //a[contains(text(),'{btn_text}')] | //span[contains(text(),'{btn_text}')]")
        for b in btns:
            if b.is_displayed():
                found_buttons.append((btn_text, b))
                print(f"  [FOUND] '{btn_text}' button: '{b.text[:50]}'")
    
    if found_buttons:
        # Clicar no primeiro Free Trial
        label, btn = found_buttons[0]
        print(f"\n  Clicando: '{label}'...")
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(0.5)
        btn.click()
        time.sleep(3)
        ss("uc_05_trial_clicked.png")
        
        # Verificar se abriu modal de confirmacao
        page_text = driver.find_element(By.TAG_NAME, "body").text
        print(f"  Texto da pagina (resumo): {page_text[:200]}")
        
        # Procurar botao de confirmar
        for confirm_sel in [
            "//button[contains(text(),'Confirm')]",
            "//button[contains(text(),'OK')]",
            "//button[contains(text(),'Submit')]",
            "button.ant-btn-primary",
            ".ant-modal-footer button.ant-btn-primary",
        ]:
            try:
                if confirm_sel.startswith("//"):
                    el = driver.find_element(By.XPATH, confirm_sel)
                else:
                    el = driver.find_element(By.CSS_SELECTOR, confirm_sel)
                if el.is_displayed():
                    print(f"  Confirmando: '{el.text}'")
                    el.click()
                    time.sleep(3)
                    ss("uc_06_confirmed.png")
                    break
            except:
                pass
    else:
        print("  Nenhum botao de trial encontrado!")
        print("  Listando TODOS os botoes da pagina:")
        all_btns = driver.find_elements(By.TAG_NAME, "button")
        for b in all_btns:
            if b.is_displayed() and b.text.strip():
                print(f"    BTN: '{b.text.strip()[:60]}'")
    
    # 4. Verificar se tem mais data centers para ativar
    print("\n[4] Verificando overview do projeto...")
    driver.get(f"https://platform.tuya.com/cloud/basic?id={PROJECT_ID}")
    time.sleep(5)
    ss("uc_07_overview.png")
    
    page_text = driver.find_element(By.TAG_NAME, "body").text
    for line in page_text.split("\n"):
        line = line.strip()
        if any(k in line.lower() for k in ["data center", "region", "america", "eastern", "western", "project", "iot core", "authorization"]):
            print(f"  INFO: {line[:120]}")
    
    # 5. Ir para Service API do projeto para verificar/autorizar
    print("\n[5] Verificando Service API do projeto...")
    driver.get(f"https://platform.tuya.com/cloud/appinfo/cappId/{PROJECT_ID}")
    time.sleep(5)
    ss("uc_08_service_api.png")
    
    page_text = driver.find_element(By.TAG_NAME, "body").text
    for line in page_text.split("\n"):
        line = line.strip()
        if any(k in line.lower() for k in ["iot core", "authorization", "subscri", "expired", "active", "trial"]):
            print(f"  API: {line[:120]}")
    
    # Procurar botao "Go to Authorize"
    for sel in [
        "//button[contains(text(),'Authorize')]",
        "//a[contains(text(),'Authorize')]",
        "//button[contains(text(),'Subscribe')]",
        "//a[contains(text(),'Subscribe')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Clicando: '{el.text}'")
                el.click()
                time.sleep(3)
                ss("uc_09_authorize.png")
                break
        except:
            pass
    
    # 6. Testar API
    print("\n[6] Testando API apos renovacao...")
    import tinytuya
    
    for region in ["us-e", "us"]:
        try:
            c = tinytuya.Cloud(
                apiRegion=region,
                apiKey="kjg5qhcsgd44uf8ppty8",
                apiSecret="5a9be7cf8a514ce39112b53045c4b96f",
                apiDeviceID="ebbc9f4aaf16cce3a4wj26"
            )
            devices = c.getdevices()
            if isinstance(devices, dict) and 'Error' in devices:
                err = devices.get('Payload', devices.get('Error', ''))
                print(f"  [{region}] Erro: {err[:100]}")
            elif isinstance(devices, list):
                print(f"  [{region}] SUCESSO! {len(devices)} dispositivos")
                for d in devices[:10]:
                    print(f"    - {d.get('name','?')} | id={d.get('id','?')} | key={d.get('key','?')}")
            else:
                print(f"  [{region}] Resposta: {str(devices)[:100]}")
        except Exception as e:
            print(f"  [{region}] Exception: {e}")
    
    print("\n" + "=" * 60)
    print("  Processo concluido!")
    print("=" * 60)
    input("\nPressione ENTER para fechar o navegador")

except Exception as e:
    print(f"\n[ERRO] {e}")
    import traceback
    traceback.print_exc()
    ss("uc_error.png")
    input("\nPressione ENTER para fechar")

finally:
    try:
        driver.quit()
        print("[OK] Chrome fechado")
    except:
        pass
