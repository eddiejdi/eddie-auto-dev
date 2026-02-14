#!/usr/bin/env python3
"""Login automatico no Tuya Platform + renovar IoT Core + vincular Smart Life"""
import time, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *

SSDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "tuya_setup")
os.makedirs(SSDIR, exist_ok=True)
n = [0]
def ss(d, name):
    n[0] += 1
    p = os.path.join(SSDIR, f"auto_{n[0]:02d}_{name}.png")
    d.save_screenshot(p)
    print(f"  [ss] {os.path.basename(p)}")

EMAIL = os.environ.get("TUYA_EMAIL", "edenilson.adm@gmail.com")
PASSWD = os.environ["TUYA_PASSWORD"]  # Required env var
PID = "p1768171340520uw8ar4"

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1400,900")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.page_load_strategy = "eager"

d = webdriver.Chrome(options=opts)
d.set_page_load_timeout(30)
d.implicitly_wait(3)
wait = WebDriverWait(d, 15)
print("[OK] Chrome aberto")

try:
    # === LOGIN ===
    print("\n[1] Login...")
    d.get("https://auth.tuya.com/?from=https://platform.tuya.com/cloud")
    time.sleep(4)
    ss(d, "login")

    # Preencher email
    email_sels = [
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='email' i]",
        "input[placeholder*='mail' i]",
        "input[placeholder*='account' i]",
        "#email",
        "input[name='username']",
    ]
    email_filled = False
    for sel in email_sels:
        try:
            el = d.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                el.clear()
                el.send_keys(EMAIL)
                email_filled = True
                print(f"  Email preenchido via: {sel}")
                break
        except NoSuchElementException:
            continue

    if not email_filled:
        # Tentar por todos os inputs visiveis
        inputs = d.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            if inp.is_displayed() and inp.get_attribute("type") in ("text", "email", ""):
                inp.clear()
                inp.send_keys(EMAIL)
                email_filled = True
                print(f"  Email preenchido no primeiro input visivel")
                break

    time.sleep(1)

    # Preencher senha
    pwd_sels = [
        "input[name='password']",
        "input[type='password']",
        "input[placeholder*='password' i]",
        "input[placeholder*='senha' i]",
        "#password",
    ]
    pwd_filled = False
    for sel in pwd_sels:
        try:
            el = d.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                el.clear()
                el.send_keys(PASSWD)
                pwd_filled = True
                print(f"  Senha preenchida via: {sel}")
                break
        except NoSuchElementException:
            continue

    if not pwd_filled:
        inputs = d.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            if inp.is_displayed() and inp.get_attribute("type") == "password":
                inp.clear()
                inp.send_keys(PASSWD)
                pwd_filled = True
                print(f"  Senha preenchida no input password")
                break

    ss(d, "credentials")
    time.sleep(1)

    # Clicar botao Login/Sign In
    login_sels = [
        "//button[contains(text(),'Log In')]",
        "//button[contains(text(),'Sign In')]",
        "//button[contains(text(),'Login')]",
        "//button[@type='submit']",
        "//input[@type='submit']",
        "//span[contains(text(),'Log In')]/..",
        "//span[contains(text(),'Sign In')]/..",
    ]
    for sel in login_sels:
        try:
            el = d.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Clicando login: '{el.text}'")
                el.click()
                break
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    time.sleep(8)
    ss(d, "after_login")
    print(f"  URL apos login: {d.current_url}")

    # Verificar se login deu certo
    if "auth" in d.current_url.lower():
        print("  [!] Ainda na pagina de auth - pode ter CAPTCHA ou erro")
        ss(d, "login_issue")
        print("  >>> Resolva manualmente e pressione ENTER <<<")
        input()
        time.sleep(2)

    # === CLOUD SERVICES ===
    print("\n[2] Cloud Services - IoT Core...")
    d.get(f"https://platform.tuya.com/cloud/products?id={PID}&productType=all")
    time.sleep(5)
    ss(d, "cloud_services")

    src = d.page_source.lower()
    for t in ["iot core", "free trial", "expired", "subscribe", "renew"]:
        if t in src:
            print(f"  '{t}' encontrado")

    # Tentar Free Trial
    for sel in [
        "//span[contains(text(),'Free Trial')]/..",
        "//button[contains(text(),'Free Trial')]",
        "//a[contains(text(),'Free Trial')]",
    ]:
        try:
            el = d.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Clicando: '{el.text}'")
                try:
                    el.click()
                except ElementClickInterceptedException:
                    d.execute_script("arguments[0].click();", el)
                time.sleep(3)
                ss(d, "trial_clicked")
                # Confirm
                for cs in ["//button[contains(text(),'Continue')]", "//button[contains(text(),'OK')]", "//button[contains(text(),'Confirm')]"]:
                    try:
                        c = d.find_element(By.XPATH, cs)
                        if c.is_displayed():
                            c.click()
                            time.sleep(2)
                            ss(d, "confirmed")
                            break
                    except NoSuchElementException:
                        continue
                break
        except NoSuchElementException:
            continue

    # === DEVICES - Link Smart Life ===
    print("\n[3] Devices - Link Smart Life...")
    d.get(f"https://platform.tuya.com/cloud/device/list?id={PID}")
    time.sleep(5)
    ss(d, "devices")

    src = d.page_source
    for t in ["Link Tuya App", "Add App Account", "Smart Life", "No Data"]:
        if t.lower() in src.lower():
            print(f"  '{t}' encontrado")

    # Clicar Link Tuya App Account
    for sel in [
        "//span[contains(text(),'Link Tuya App Account')]",
        "//div[contains(text(),'Link Tuya App Account')]",
        "//span[contains(text(),'Link Tuya App')]",
    ]:
        try:
            el = d.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Clicando: '{el.text}'")
                el.click()
                time.sleep(3)
                ss(d, "link_tab")
                break
        except NoSuchElementException:
            continue

    # Clicar Add App Account
    for sel in [
        "//span[contains(text(),'Add App Account')]/..",
        "//button[contains(text(),'Add App Account')]",
    ]:
        try:
            el = d.find_element(By.XPATH, sel)
            if el.is_displayed():
                print(f"  Clicando: '{el.text}'")
                el.click()
                time.sleep(3)
                ss(d, "qr_code")
                print("\n  >>> QR CODE EXIBIDO <<<")
                print("  Escaneie com o app Smart Life e pressione ENTER")
                input()
                time.sleep(3)
                ss(d, "after_qr")
                break
        except NoSuchElementException:
            continue

    # === TESTAR API ===
    print("\n[4] Testando API...")
    d.get(f"https://platform.tuya.com/cloud/device/list?id={PID}")
    time.sleep(5)
    ss(d, "final_devices")

    # Contar dispositivos na tabela
    rows = d.find_elements(By.CSS_SELECTOR, "table tbody tr, .ant-table-row")
    print(f"  Dispositivos na tabela: {len(rows)}")
    for r in rows[:10]:
        print(f"    -> {r.text[:120]}")

    print("\n[OK] Processo concluido!")
    print("Pressione ENTER para fechar")
    input()

except Exception as e:
    print(f"\n[ERRO] {e}")
    ss(d, "error")
    print("Pressione ENTER para fechar")
    input()

d.quit()
print("[OK] Chrome fechado")
