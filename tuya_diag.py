#!/usr/bin/env python3
"""
Diagnostico completo da plataforma Tuya - encontrar onde renovar IoT Core.
Usa sessao salva do perfil persistente.
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

PROFILE_DIR = os.path.expanduser("~/.tuya_chrome_profile")
PROJECT_ID = "p1768171340520uw8ar4"
SS_DIR = "/home/edenilson/eddie-auto-dev/screenshots"

opts = Options()
opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
opts.add_argument("--no-sandbox")
opts.add_argument("--start-maximized")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])

driver = webdriver.Chrome(options=opts)

def ss(name):
    driver.save_screenshot(f"{SS_DIR}/{name}")
    print(f"  [ss] {name}")

def dump_page(label):
    """Captura texto completo da pagina."""
    text = driver.find_element(By.TAG_NAME, "body").text
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    print(f"\n  --- {label} ({len(lines)} linhas) ---")
    for i, line in enumerate(lines[:80]):
        print(f"  {i:3d}: {line[:120]}")
    if len(lines) > 80:
        print(f"  ... +{len(lines)-80} linhas")

try:
    # 1. Verificar sessao
    print("[1] Verificando sessao...")
    driver.get("https://platform.tuya.com/cloud")
    time.sleep(5)
    
    if "auth.tuya.com" in driver.current_url:
        print("  ERRO: Sessao expirada!")
        exit(1)
    
    print(f"  URL: {driver.current_url}")
    print("  [OK] Sessao ativa")
    ss("diag_01_cloud.png")
    dump_page("Cloud Main")
    
    # 2. Tentar varias URLs de Cloud Services
    urls_to_try = [
        ("Cloud Services", "https://platform.tuya.com/cloud/services"),
        ("Cloud Products", "https://platform.tuya.com/cloud/products"),
        ("Cloud Explorer", "https://platform.tuya.com/cloud/explorer"),
        ("Cloud Service List", "https://platform.tuya.com/cloud/service-list"),
        ("IoT Core Direct", "https://platform.tuya.com/cloud/services/iot-core"),
        ("Project Overview", f"https://platform.tuya.com/cloud/basic?id={PROJECT_ID}"),
        ("Project Service API", f"https://platform.tuya.com/cloud/appinfo/cappId/{PROJECT_ID}"),
        ("Project Devices", f"https://platform.tuya.com/cloud/device/list?id={PROJECT_ID}"),
    ]
    
    for label, url in urls_to_try:
        print(f"\n[{label}]")
        driver.get(url)
        time.sleep(4)
        
        final_url = driver.current_url
        print(f"  URL final: {final_url}")
        
        name = label.replace(" ", "_").lower()
        ss(f"diag_{name}.png")
        
        # Procurar IoT Core
        page = driver.find_element(By.TAG_NAME, "body").text
        if "iot core" in page.lower():
            print(f"  >>> IoT Core ENCONTRADO! <<<")
            dump_page(label)
            
            # Procurar botoes
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for b in buttons:
                txt = b.text.strip()
                if txt:
                    print(f"    BTN: '{txt}' visible={b.is_displayed()}")
        
        # Verificar links de navegacao no sidebar
        nav_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='cloud'], nav a, .ant-menu a, [class*='sidebar'] a, [class*='menu'] a")
        if nav_links:
            seen = set()
            for a in nav_links[:30]:
                href = a.get_attribute("href") or ""
                txt = a.text.strip()
                key = f"{txt}|{href}"
                if txt and key not in seen and "cloud" in href.lower():
                    seen.add(key)
                    print(f"    NAV: '{txt}' -> {href[:80]}")
    
    # 3. Procurar sidebar/menu de navegacao na pagina principal do projeto
    print("\n[3] Explorando menu do projeto...")
    driver.get(f"https://platform.tuya.com/cloud/basic?id={PROJECT_ID}")
    time.sleep(5)
    ss("diag_project_menu.png")
    dump_page("Project Menu")
    
    # Pegar todos os links
    all_links = driver.find_elements(By.TAG_NAME, "a")
    print(f"\n  Todos os links ({len(all_links)}):")
    seen = set()
    for a in all_links:
        href = a.get_attribute("href") or ""
        txt = a.text.strip()
        if href and txt and href not in seen:
            seen.add(href)
            print(f"    '{txt}' -> {href[:100]}")

except Exception as e:
    print(f"\n[ERRO] {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()
    print("\n[OK] Chrome fechado")
