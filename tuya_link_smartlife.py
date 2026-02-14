#!/usr/bin/env python3
"""Ativar Data Center e vincular Smart Life no Tuya Platform."""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1400,900")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.page_load_strategy = "eager"

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(45)
driver.implicitly_wait(3)
print("[1] Chrome OK")

try:
    # Ir para Overview do projeto agent
    url = "https://platform.tuya.com/cloud/basic?id=p1768171340520uw8ar4"
    print(f"[2] Navegando: {url}")
    driver.get(url)
    time.sleep(5)
    cur = driver.current_url
    print(f"    URL: {cur}")

    if "auth" in cur.lower():
        print("\n>>> FACA LOGIN no navegador <<<")
        print(">>> Depois pressione ENTER aqui <<<")
        input()
        time.sleep(2)
        driver.get(url)
        time.sleep(5)
        print(f"    URL pos-login: {driver.current_url}")

    driver.save_screenshot("screenshots/tuya_setup/overview.png")

    print("\n============================================")
    print(" A API retornou: 'Data center is suspended'")
    print(" Voce precisa:")
    print("")
    print(" 1. No projeto 'agent', va em Overview")
    print(" 2. Procure 'Data Center' ou 'Authorization'")
    print(" 3. ATIVE o Data Center 'Eastern America'")
    print(" 4. Verifique se as APIs estao autorizadas:")
    print("    - IoT Core")
    print("    - Smart Home Device Management")
    print("    - Authorization Token Management")
    print(" 5. Verifique aba 'Devices' se Smart Life")
    print("    esta vinculado (deve ter dispositivos)")
    print("")
    print(" Pressione ENTER quando tudo estiver OK")
    print("============================================")
    input()

    time.sleep(3)
    driver.save_screenshot("screenshots/tuya_setup/step3_linked.png")
    print("[5] OK - Smart Life vinculado")

except Exception as e:
    print(f"Erro: {e}")
    driver.save_screenshot("screenshots/tuya_setup/error.png")

print("\nPressione ENTER para fechar Chrome")
input()
driver.quit()
print("Done")
