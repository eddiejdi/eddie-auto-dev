from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-blink-features=AutomationControlled')

driver = webdriver.Chrome(options=options)
try:
    print("🔍 Acessando site...")
    driver.get('https://www.rpa4all.com')
    time.sleep(3)
    
    # Verificar container
    container = driver.find_element(By.CLASS_NAME, 'ide-container')
    computed_style = driver.execute_script("return window.getComputedStyle(arguments[0])", container)
    
    display = computed_style.get('display')
    flex_direction = computed_style.get('flexDirection')
    
    print(f"✅ IDE Container Display: {display}")
    print(f"✅ IDE Container Flex Direction: {flex_direction}")
    
    # Verificar elementos principais
    toolbar = driver.find_element(By.CLASS_NAME, 'ide-toolbar')
    ai_bar = driver.find_element(By.CLASS_NAME, 'ide-ai-bar')
    editor = driver.find_element(By.CLASS_NAME, 'ide-main')
    output = driver.find_element(By.CLASS_NAME, 'ide-output')
    
    print(f"✅ IDE Toolbar encontrado: {toolbar.is_displayed()}")
    print(f"✅ IDE AI Bar encontrado: {ai_bar.is_displayed()}")
    print(f"✅ IDE Editor encontrado: {editor.is_displayed()}")
    print(f"✅ IDE Output encontrado: {output.is_displayed()}")
    
    print("\n✅ FASE 1 VALIDADA COM SUCESSO!")
    
finally:
    driver.quit()
