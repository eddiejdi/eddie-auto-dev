#!/usr/bin/env python3
"""
Vincular conta Smart Life ao projeto Tuya 'agent'.
Navega para Devices > Link Tuya App Account > Add App Account > QR Code
"""
import time, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "tuya_setup")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
n = [0]

def ss(driver, name):
    n[0] += 1
    p = os.path.join(SCREENSHOT_DIR, f"link_{n[0]:02d}_{name}.png")
    driver.save_screenshot(p)
    print(f"  [ss] {os.path.basename(p)}")

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

PID = "p1768171340520uw8ar4"

try:
    # Login
    driver.get(f"https://platform.tuya.com/cloud/basic?id={PID}")
    time.sleep(5)

    if "auth" in driver.current_url.lower():
        ss(driver, "login")
        print(">>> FACA LOGIN e pressione ENTER <<<")
        input()
        time.sleep(3)
        driver.get(f"https://platform.tuya.com/cloud/basic?id={PID}")
        time.sleep(5)

    ss(driver, "overview")
    print(f"URL: {driver.current_url}")

    # Clicar na aba Devices
    print("\n=== Navegando para aba Devices ===")
    tabs = driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .ant-tabs-tab, a[class*='tab']")
    for tab in tabs:
        if "device" in tab.text.lower():
            print(f"  Aba: '{tab.text}'")
            tab.click()
            time.sleep(3)
            break
    else:
        # Tentar URL direta - formato correto
        driver.get(f"https://platform.tuya.com/cloud/basic?id={PID}&tab=device")
        time.sleep(3)

    ss(driver, "devices_tab")
    print(f"URL: {driver.current_url}")

    # Procurar sub-aba "Link Tuya App Account"
    print("\n=== Procurando Link Tuya App Account ===")
    link_xpaths = [
        "//div[contains(text(),'Link Tuya App Account')]",
        "//span[contains(text(),'Link Tuya App Account')]",
        "//div[contains(@class,'tab')]//span[contains(text(),'App Account')]",
        "//div[contains(text(),'App Account')]",
        "//*[contains(text(),'Tuya App Account')]",
    ]

    for xp in link_xpaths:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    print(f"  Encontrado: '{el.text}'")
                    el.click()
                    time.sleep(3)
                    ss(driver, "app_account_tab")
                    break
        except Exception:
            continue

    # Procurar "Add App Account"
    print("\n=== Procurando Add App Account ===")
    add_xpaths = [
        "//span[contains(text(),'Add App Account')]/..",
        "//button[contains(text(),'Add App Account')]",
        "//a[contains(text(),'Add App Account')]",
        "//span[contains(text(),'Add App')]/..",
    ]

    for xp in add_xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el.is_displayed():
                print(f"  Botao: '{el.text}'")
                try:
                    el.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(3)
                ss(driver, "qr_code")
                print("\n  >>> QR CODE exibido! Escaneie com Smart Life <<<")
                print("  >>> Pressione ENTER apos escanear <<<")
                input()
                time.sleep(3)
                ss(driver, "after_scan")

                # Confirmar linking
                confirm_xpaths = [
                    "//button[contains(text(),'OK')]",
                    "//span[contains(text(),'OK')]/..",
                    "//button[contains(text(),'Confirm')]",
                ]
                for cx in confirm_xpaths:
                    try:
                        cb = driver.find_element(By.XPATH, cx)
                        if cb.is_displayed():
                            cb.click()
                            time.sleep(2)
                            ss(driver, "confirmed")
                            print("  [OK] Confirmado!")
                            break
                    except Exception:
                        continue
                break
        except NoSuchElementException:
            continue

    # Mostrar resultado
    print("\n=== Estado final ===")
    ss(driver, "final")
    src = driver.page_source
    for term in ["Smart Life", "device", "linked", "online", "offline"]:
        if term.lower() in src.lower():
            print(f"  '{term}' presente na pagina")

    # Listar dispositivos visiveis
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .ant-table-row")
    print(f"  Linhas de dispositivos: {len(rows)}")
    for r in rows[:10]:
        print(f"    -> {r.text[:120]}")

    print("\nPressione ENTER para fechar")
    input()

except Exception as e:
    print(f"[ERRO] {e}")
    ss(driver, "error")
    print("Pressione ENTER para fechar")
    input()

driver.quit()
print("[OK] Done")
