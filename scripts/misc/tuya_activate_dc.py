#!/usr/bin/env python3
"""
Ativar Data Center no projeto Tuya e listar dispositivos.
Navega automaticamente para as páginas necessárias.
"""
import time, json, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "tuya_setup")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def ss(driver, name):
    p = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    driver.save_screenshot(p)
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
driver.set_page_load_timeout(45)
driver.implicitly_wait(3)
print("[OK] Chrome iniciado")

try:
    # 1. Login
    driver.get("https://platform.tuya.com/cloud/basic?id=p1768171340520uw8ar4")
    time.sleep(5)

    if "auth" in driver.current_url.lower():
        ss(driver, "s1_login")
        print("\n>>> FACA LOGIN no navegador e pressione ENTER <<<")
        input()
        time.sleep(2)
        driver.get("https://platform.tuya.com/cloud/basic?id=p1768171340520uw8ar4")
        time.sleep(5)

    ss(driver, "s2_overview")
    print(f"[OK] Pagina: {driver.current_url}")

    # 2. Extrair info da pagina
    src = driver.page_source
    print(f"[INFO] Titulo: {driver.title}")

    # Procurar textos sobre Data Center na pagina
    for text in ["suspended", "Enable", "Activate", "Data Center", "Eastern America",
                  "Smart Life", "device", "Linked", "Authorization"]:
        if text.lower() in src.lower():
            print(f"  Encontrado na pagina: '{text}'")

    # 3. Procurar botao Enable Data Center
    enable_sels = [
        "//button[contains(text(),'Enable')]",
        "//a[contains(text(),'Enable')]",
        "//span[contains(text(),'Enable')]/..",
        "//button[contains(text(),'Activate')]",
        "//button[contains(text(),'Open')]",
        "//span[contains(text(),'Activate')]/..",
    ]

    for sel in enable_sels:
        try:
            el = driver.find_element(By.XPATH, sel)
            print(f"  Botao encontrado: {sel} -> {el.text}")
            el.click()
            print(f"  [OK] Clicou Enable!")
            time.sleep(3)
            ss(driver, "s3_enabled")
            break
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    # 4. Navegar para aba Devices
    print("\n[PASSO] Navegando para Devices...")
    driver.get("https://platform.tuya.com/cloud/device/list?id=p1768171340520uw8ar4")
    time.sleep(5)
    ss(driver, "s4_devices")
    print(f"[INFO] URL Devices: {driver.current_url}")

    src = driver.page_source
    for text in ["Smart Life", "Link", "device", "No Data", "No Device"]:
        if text.lower() in src.lower():
            print(f"  Devices page: '{text}' encontrado")

    # 5. Verificar se ha dispositivos listados
    # Procurar tabela com dispositivos
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .ant-table-row, [class*='device']")
        print(f"  Linhas de dispositivos: {len(rows)}")
        for r in rows[:10]:
            print(f"    -> {r.text[:100]}")
    except Exception:
        pass

    # 6. Tentar listar APIs autorizadas
    print("\n[PASSO] Verificando APIs...")
    driver.get("https://platform.tuya.com/cloud/appinfo/cappId/p1768171340520uw8ar4")
    time.sleep(5)
    ss(driver, "s5_apis")

    src = driver.page_source
    apis = ["IoT Core", "Smart Home", "Authorization", "Device Management", "Scene"]
    for api in apis:
        if api.lower() in src.lower():
            print(f"  API '{api}' presente na pagina")

    print("\n============================================")
    print(" ACOES NECESSARIAS no navegador aberto:")
    print("")
    print(" 1. Verifique se Data Center esta ATIVADO")
    print("    (Overview -> Data Center -> Enable)")
    print("")
    print(" 2. Verifique APIs autorizadas")
    print("    (API -> IoT Core, Device Mgmt)")
    print("")
    print(" 3. Vincule Smart Life se nao vinculou")
    print("    (Devices -> Link Tuya App Account)")
    print("")
    print(" Pressione ENTER quando tudo OK")
    print("============================================")
    input()

    ss(driver, "s6_final")

except Exception as e:
    print(f"Erro: {e}")
    ss(driver, "error")

print("\nPressione ENTER para fechar")
input()
driver.quit()
print("Done")
