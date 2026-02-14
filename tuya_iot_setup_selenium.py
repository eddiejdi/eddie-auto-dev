#!/usr/bin/env python3
"""
Tuya Developer Platform Setup via Selenium
Modo VISIVEL — usuario interage diretamente no navegador.
Timestamp: 2026-02-12
"""
import os, sys, json, time, re
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

BASE = os.path.dirname(os.path.abspath(__file__))
SSDIR = os.path.join(BASE, "screenshots", "tuya_setup")
os.makedirs(SSDIR, exist_ok=True)

def ts():
    return datetime.now().strftime("%H:%M:%S")

def ss(d, name):
    p = os.path.join(SSDIR, f"{datetime.now().strftime('%H%M%S')}_{name}.png")
    d.save_screenshot(p)
    print(f"  [{ts()}] SS: {p}")

def try_click(driver, selectors):
    for sel in selectors:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            el = driver.find_element(by, sel)
            try:
                el.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", el)
            return el, sel
        except (NoSuchElementException, ElementClickInterceptedException):
            continue
    return None, None

print(f"[{ts()}] === TUYA SETUP VIA SELENIUM ===")
print(f"[{ts()}] Email: edenilson.adm@gmail.com")

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1400,900")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.page_load_strategy = "eager"

print(f"[{ts()}] Abrindo Chrome...")
driver = webdriver.Chrome(options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})
driver.set_page_load_timeout(45)
driver.implicitly_wait(3)
print(f"[{ts()}] Chrome OK")

try:
    # === FASE 1: LOGIN ===
    print(f"\n[{ts()}] === FASE 1: LOGIN ===")
    driver.get("https://auth.tuya.com/?from=https%3A%2F%2Fiot.tuya.com")
    time.sleep(4)
    ss(driver, "01_auth")
    print(f"[{ts()}] URL: {driver.current_url}")

    # Auto-preencher email
    for sel in ["input[name='email']", "input[type='email']", "input[placeholder*='email']", "input[placeholder*='Email']", "input[placeholder*='account']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.clear()
            el.send_keys("edenilson.adm@gmail.com")
            print(f"[{ts()}] Email preenchido automaticamente")
            break
        except NoSuchElementException:
            continue

    print(f"\n[{ts()}] >>> FACA LOGIN NO NAVEGADOR <<<")
    print(f"[{ts()}] >>> Digite sua senha, resolva captcha <<<")
    print(f"[{ts()}] >>> Script detecta automaticamente quando logar <<<\n")

    # Aguardar login (max 5 min)
    for i in range(150):
        time.sleep(2)
        url = driver.current_url
        if "auth.tuya.com" not in url and "login" not in url.lower():
            print(f"[{ts()}] Login detectado! URL: {url}")
            break
        if i % 15 == 0 and i > 0:
            print(f"[{ts()}] Aguardando login... ({i*2}s)")
    else:
        print(f"[{ts()}] Timeout login")
        ss(driver, "timeout")
        sys.exit(1)

    time.sleep(2)
    ss(driver, "02_logged")

    # === FASE 2: CLOUD PROJECT ===
    print(f"\n[{ts()}] === FASE 2: CLOUD PROJECT ===")
    driver.get("https://platform.tuya.com/cloud")
    time.sleep(5)
    ss(driver, "03_cloud")
    print(f"[{ts()}] URL: {driver.current_url}")

    src = driver.page_source
    if "Eddie Home" in src:
        print(f"[{ts()}] Projeto 'Eddie Home' existe!")
    else:
        print(f"\n[{ts()}] >>> CRIE CLOUD PROJECT NO NAVEGADOR <<<")
        print(f"[{ts()}]   Nome: Eddie Home | Industry: Smart Home")
        print(f"[{ts()}]   Data Center: Central/Western America")
        print(f"[{ts()}]   APIs: IoT Core + Smart Home Device Management")
        print(f"[{ts()}] >>> Aguardando... <<<\n")

        for i in range(150):
            time.sleep(2)
            if "Eddie" in driver.page_source or "overview" in driver.current_url.lower():
                print(f"[{ts()}] Projeto detectado!")
                break
            if i % 15 == 0 and i > 0:
                print(f"[{ts()}] Aguardando projeto... ({i*2}s)")

    time.sleep(2)
    ss(driver, "04_project")

    # === FASE 3: VINCULAR SMART LIFE ===
    print(f"\n[{ts()}] === FASE 3: VINCULAR SMART LIFE ===")
    try_click(driver, ["//a[contains(text(),'Devices')]", "//span[contains(text(),'Devices')]", "a[href*='device']"])
    time.sleep(2)
    try_click(driver, ["//a[contains(text(),'Link')]", "//button[contains(text(),'Link')]", "//button[contains(text(),'Add')]"])
    time.sleep(2)
    ss(driver, "05_devices")

    print(f"\n[{ts()}] >>> VINCULE SMART LIFE VIA QR CODE <<<")
    print(f"[{ts()}]   Smart Life app -> Perfil -> Escanear QR")
    print(f"[{ts()}] >>> Aguardando... <<<\n")

    for i in range(150):
        time.sleep(2)
        low = driver.page_source.lower()
        if low.count("online") > 0 or "device id" in low:
            print(f"[{ts()}] Dispositivos detectados!")
            break
        if i % 15 == 0 and i > 0:
            print(f"[{ts()}] Aguardando vinculacao... ({i*2}s)")

    time.sleep(2)
    ss(driver, "06_linked")

    # === FASE 4: CREDENCIAIS ===
    print(f"\n[{ts()}] === FASE 4: EXTRAIR CREDENCIAIS ===")
    try_click(driver, ["//a[contains(text(),'Overview')]", "//span[contains(text(),'Overview')]", "a[href*='overview']"])
    time.sleep(3)
    ss(driver, "07_overview")

    src = driver.page_source
    access_id = None
    access_secret = None

    for pat in [r'(?:Access\s*ID|Client\s*ID)[^a-zA-Z0-9]*([a-zA-Z0-9]{16,32})']:
        m = re.search(pat, src, re.IGNORECASE)
        if m:
            access_id = m.group(1)
            print(f"[{ts()}] Access ID: {access_id[:8]}...")
            break

    for pat in [r'(?:Access\s*Secret|Client\s*Secret)[^a-zA-Z0-9]*([a-zA-Z0-9]{16,64})']:
        m = re.search(pat, src, re.IGNORECASE)
        if m:
            access_secret = m.group(1)
            print(f"[{ts()}] Access Secret: {access_secret[:8]}...")
            break

    if not access_id:
        print(f"[{ts()}] Cole o Access ID da Overview:")
        access_id = input(f"Access ID: ").strip()
    if not access_secret:
        print(f"[{ts()}] Cole o Access Secret (clique olho/copiar):")
        access_secret = input(f"Access Secret: ").strip()

    driver.quit()
    print(f"[{ts()}] Chrome fechado")

    if not access_id or not access_secret:
        print(f"[{ts()}] Credenciais incompletas!")
        sys.exit(1)

    creds = {
        "access_id": access_id,
        "access_secret": access_secret,
        "region": "us",
        "email": "edenilson.adm@gmail.com",
        "project_name": "Eddie Home",
        "created_at": datetime.now().isoformat(),
    }
    with open(os.path.join(BASE, "tuya_credentials.json"), "w") as f:
        json.dump(creds, f, indent=2)
    print(f"[{ts()}] Credenciais salvas: tuya_credentials.json")

    # === FASE 5: TINYTUYA ===
    print(f"\n[{ts()}] === FASE 5: TINYTUYA ===")
    import tinytuya
    print(f"[{ts()}] tinytuya v{tinytuya.__version__}")

    c = tinytuya.Cloud(apiRegion="us", apiKey=access_id, apiSecret=access_secret)
    devices = c.getdevices()

    if isinstance(devices, list) and len(devices) > 0:
        print(f"[{ts()}] {len(devices)} dispositivo(s):")
        dlist = []
        for i, d in enumerate(devices, 1):
            name = d.get("name", "?")
            cat = d.get("category", "?")
            key = d.get("key", "?")
            print(f"  {i}. {name} [{cat}] key={key[:8]}...")
            dlist.append({"name": name, "id": d.get("id",""), "key": key, "category": cat, "ip": "", "product_name": d.get("product_name","")})

        print(f"\n[{ts()}] Scan rede local...")
        try:
            scan = tinytuya.deviceScan(verbose=False, maxretry=3)
            if scan:
                for did, info in scan.items():
                    for d in dlist:
                        if d["id"] == did:
                            d["ip"] = info.get("ip", "")
                            d["version"] = info.get("version", "")
                            print(f"  {d['name']}: {d['ip']} (v{d.get('version','')})")
        except Exception as e:
            print(f"  Scan: {e}")

        with open(os.path.join(BASE, "tuya_devices.json"), "w") as f:
            json.dump(dlist, f, indent=2, ensure_ascii=False)
        print(f"\n[{ts()}] COMPLETO! {len(dlist)} dispositivos em tuya_devices.json")
    else:
        print(f"[{ts()}] API retornou: {devices}")

except KeyboardInterrupt:
    print(f"\n[{ts()}] Interrompido")
except SystemExit:
    pass
except Exception as e:
    print(f"\n[{ts()}] Erro: {e}")
    import traceback
    traceback.print_exc()
    try:
        ss(driver, "error")
    except:
        pass
finally:
    try:
        driver.quit()
    except:
        pass
