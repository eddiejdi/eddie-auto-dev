#!/usr/bin/env python3
"""
SOLUÇÃO DEFINITIVA: Ativar função via interface web usando Selenium
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

WEBUI_URL = "http://192.168.15.2:8002"
EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie@2026"

# Configurar Chrome headless
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=chrome_options)

try:
    print("1️⃣ Acessando Open WebUI...")
    driver.get(WEBUI_URL)
    time.sleep(2)
    
    print("2️⃣ Fazendo login...")
    email_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
    )
    email_input.send_keys(EMAIL)
    
    password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    password_input.send_keys(PASSWORD)
    
    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()
    time.sleep(3)
    
    print("3️⃣ Navegando para Functions...")
    driver.get(f"{WEBUI_URL}/admin/functions")
    time.sleep(2)
    
    print("4️⃣ Procurando função de impressora...")
    # Procurar por elemento que contenha "Impressora"
    functions = driver.find_elements(By.XPATH, "//*[contains(text(), 'Impressora')]")
    
    if not functions:
        print("❌ Função não encontrada na lista")
    else:
        print(f"✅ Encontrada! Total: {len(functions)}")
        
        # Procurar toggle/switch
        print("5️⃣ Procurando botão de ativação...")
        toggles = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], button.toggle, .toggle-switch")
        
        for toggle in toggles:
            if not toggle.is_selected():
                print("6️⃣ Ativando função...")
                toggle.click()
                time.sleep(1)
                print("✅ Função ativada!")
                break
        
        # Salvar se necessário
        save_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Save') or contains(text(), 'Salvar')]")
        if save_buttons:
            print("7️⃣ Salvando alterações...")
            save_buttons[0].click()
            time.sleep(2)
            print("✅ Alterações salvas!")
    
    print("\n✅ CONCLUÍDO!")
    print("Agora teste no chat: 'Imprima TESTE 123'")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    driver.save_screenshot("/tmp/webui_error.png")
    print("Screenshot salvo em /tmp/webui_error.png")
finally:
    driver.quit()
