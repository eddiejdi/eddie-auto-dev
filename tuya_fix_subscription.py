#!/usr/bin/env python3
"""
Corrigir erro 28841107 "Data Center Suspended" no Tuya IoT Platform.

CAUSA: A assinatura do IoT Core (Trial Edition) expirou.
SOLUCAO: Renovar o Free Trial em Cloud > Cloud Services > IoT Core.

Passos automatizados:
1. Navegar para Cloud Services
2. Encontrar IoT Core
3. Clicar Free Trial / Renew
4. Autorizar o projeto "agent"
"""
import time, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    ElementClickInterceptedException, StaleElementReferenceException
)

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "tuya_setup")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
counter = [0]

def ss(driver, name):
    counter[0] += 1
    p = os.path.join(SCREENSHOT_DIR, f"fix_{counter[0]:02d}_{name}.png")
    driver.save_screenshot(p)
    print(f"  [screenshot] {p}")
    return p

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1400,900")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.page_load_strategy = "eager"

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)
driver.implicitly_wait(5)
print("[OK] Chrome iniciado")

PROJECT_ID = "p1768171340520uw8ar4"

try:
    # ========================================
    # PASSO 1: Login
    # ========================================
    print("\n=== PASSO 1: Login ===")
    driver.get("https://platform.tuya.com/cloud")
    time.sleep(5)

    if "auth" in driver.current_url.lower() or "login" in driver.current_url.lower():
        ss(driver, "login_page")
        print("\n>>> FACA LOGIN no navegador e pressione ENTER <<<")
        input()
        time.sleep(3)

    ss(driver, "after_login")
    print(f"  URL: {driver.current_url}")

    # ========================================
    # PASSO 2: Navegar para Cloud Services (IoT Core)
    # ========================================
    print("\n=== PASSO 2: Cloud Services - IoT Core ===")
    # URL direta para Cloud Services
    driver.get("https://platform.tuya.com/cloud/products?productType=all")
    time.sleep(5)
    ss(driver, "cloud_services")
    print(f"  URL: {driver.current_url}")

    # Procurar IoT Core na pagina
    src = driver.page_source.lower()
    for term in ["iot core", "free trial", "subscribe", "expired", "renew", "trial edition"]:
        if term in src:
            print(f"  Encontrado: '{term}'")

    # Tentar clicar em Free Trial ou Subscribe
    trial_clicks = [
        "//span[contains(text(),'Free Trial')]/..",
        "//button[contains(text(),'Free Trial')]",
        "//a[contains(text(),'Free Trial')]",
        "//span[contains(text(),'Trial')]/..",
        "//button[contains(text(),'Subscribe')]",
        "//a[contains(text(),'Subscribe')]",
        "//span[contains(text(),'Renew')]/..",
        "//button[contains(text(),'Renew')]",
    ]

    clicked = False
    for sel in trial_clicks:
        try:
            els = driver.find_elements(By.XPATH, sel)
            for el in els:
                if el.is_displayed():
                    print(f"  Botao encontrado: '{el.text}' via {sel}")
                    try:
                        el.click()
                        clicked = True
                        time.sleep(3)
                        ss(driver, "after_trial_click")
                        break
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", el)
                        clicked = True
                        time.sleep(3)
                        ss(driver, "after_trial_js_click")
                        break
            if clicked:
                break
        except (NoSuchElementException, StaleElementReferenceException):
            continue

    if not clicked:
        print("\n  [!] Nao encontrou botao Free Trial automaticamente.")
        print("  Procurando IoT Core na lista de servicos...")

        # Procurar card do IoT Core
        iot_core_sels = [
            "//*[contains(text(),'IoT Core')]",
            "//div[contains(@class,'card')]//span[contains(text(),'IoT')]/..",
            "//h3[contains(text(),'IoT Core')]",
            "//div[contains(text(),'IoT Core')]",
        ]

        for sel in iot_core_sels:
            try:
                els = driver.find_elements(By.XPATH, sel)
                for el in els:
                    if el.is_displayed():
                        print(f"  IoT Core encontrado: '{el.text[:60]}'")
                        # Procurar View Details ou link proximo
                        parent = el.find_element(By.XPATH, "./ancestor::div[contains(@class,'card') or contains(@class,'item') or contains(@class,'row')]")
                        links = parent.find_elements(By.TAG_NAME, "a") + parent.find_elements(By.TAG_NAME, "button")
                        for link in links:
                            txt = link.text.lower()
                            if any(w in txt for w in ["detail", "trial", "subscribe", "view", "open"]):
                                print(f"    -> Clicando: '{link.text}'")
                                link.click()
                                clicked = True
                                time.sleep(3)
                                ss(driver, "iot_core_detail")
                                break
                    if clicked:
                        break
            except Exception:
                continue
            if clicked:
                break

    # ========================================
    # PASSO 3: Se tiver dialog de confirmacao
    # ========================================
    if clicked:
        print("\n=== PASSO 3: Confirmar Trial ===")
        confirm_sels = [
            "//button[contains(text(),'Continue')]",
            "//button[contains(text(),'Confirm')]",
            "//button[contains(text(),'OK')]",
            "//span[contains(text(),'Continue')]/..",
            "//span[contains(text(),'Confirm')]/..",
        ]

        for sel in confirm_sels:
            try:
                el = driver.find_element(By.XPATH, sel)
                if el.is_displayed():
                    print(f"  Confirmando: '{el.text}'")
                    el.click()
                    time.sleep(3)
                    ss(driver, "confirmed")
                    break
            except (NoSuchElementException, ElementClickInterceptedException):
                continue

    # ========================================
    # PASSO 4: Autorizar projeto
    # ========================================
    print("\n=== PASSO 4: Autorizar projeto 'agent' ===")
    # Navegar para Service API do projeto
    driver.get(f"https://platform.tuya.com/cloud/appinfo/cappId/{PROJECT_ID}")
    time.sleep(5)
    ss(driver, "project_api")
    print(f"  URL: {driver.current_url}")

    # Procurar Go to Authorize
    auth_sels = [
        "//span[contains(text(),'Go to Authorize')]/..",
        "//a[contains(text(),'Go to Authorize')]",
        "//button[contains(text(),'Authorize')]",
        "//span[contains(text(),'Authorize')]/..",
    ]

    for sel in auth_sels:
        try:
            el = driver.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Autorizacao: '{el.text}'")
                el.click()
                time.sleep(3)
                ss(driver, "authorize_page")
                break
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    # ========================================
    # PASSO 5: Verificar Devices e Smart Life link
    # ========================================
    print("\n=== PASSO 5: Verificar Devices/Smart Life ===")
    driver.get(f"https://platform.tuya.com/cloud/device/list?id={PROJECT_ID}")
    time.sleep(5)
    ss(driver, "devices_page")

    src = driver.page_source
    for term in ["Smart Life", "Link Tuya App", "No Data", "device", "Add App Account"]:
        if term.lower() in src.lower():
            print(f"  Devices: '{term}' encontrado")

    # Procurar Link Tuya App Account
    link_sels = [
        "//span[contains(text(),'Link Tuya App Account')]/..",
        "//div[contains(text(),'Link Tuya App Account')]",
        "//button[contains(text(),'Link Tuya App')]",
        "//a[contains(text(),'Link Tuya App')]",
        "//span[contains(text(),'Add App Account')]/..",
    ]

    for sel in link_sels:
        try:
            el = driver.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Link Smart Life: '{el.text}'")
                el.click()
                time.sleep(3)
                ss(driver, "link_smartlife")

                # Procurar Add App Account
                try:
                    add_btn = driver.find_element(By.XPATH, "//span[contains(text(),'Add App Account')]/..")
                    if add_btn.is_displayed():
                        print(f"  Clicando Add App Account...")
                        add_btn.click()
                        time.sleep(3)
                        ss(driver, "qr_code")
                        print("\n  >>> QR CODE exibido! Escaneie com o app Smart Life <<<")
                except NoSuchElementException:
                    pass
                break
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    # ========================================
    # INSTRUCOES FINAIS
    # ========================================
    print("\n" + "="*60)
    print(" INSTRUCOES - Resolva o erro 'Data Center Suspended':")
    print("="*60)
    print()
    print(" O erro 28841107 significa que a assinatura IoT Core")
    print(" expirou. Para corrigir:")
    print()
    print(" 1. VA EM: Cloud > Cloud Services (menu lateral)")
    print("    URL: https://platform.tuya.com/cloud/products")
    print()
    print(" 2. ENCONTRE 'IoT Core' na lista")
    print()
    print(" 3. CLIQUE 'Free Trial' ou 'Subscribe to Resource Pack'")
    print("    (se Trial expirou, crie um NOVO projeto pode ser")
    print("     necessario, ou renove a assinatura)")
    print()
    print(" 4. AUTORIZE o projeto 'agent' para usar IoT Core:")
    print("    Cloud > Development > agent > Service API > Authorize")
    print()
    print(" 5. VA EM Devices > Link Tuya App Account > Add App Account")
    print("    Escaneie o QR code com o Smart Life")
    print()
    print(" ALTERNATIVA: Crie um projeto NOVO (Development > Create)")
    print("    Projetos novos ganham Trial automaticamente")
    print("="*60)
    print()
    print(" Pressione ENTER quando concluir os passos acima")
    input()

    ss(driver, "final")
    print(f"\n[INFO] URL final: {driver.current_url}")
    print(f"[INFO] Titulo: {driver.title}")

except Exception as e:
    print(f"\n[ERRO] {e}")
    ss(driver, "error")

print("\nPressione ENTER para fechar o navegador")
input()
driver.quit()
print("[OK] Finalizado")
