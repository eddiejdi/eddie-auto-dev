#!/usr/bin/env python3
"""Validação com force refresh para evitar cache"""

import sys
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
except ImportError:
    print("❌ Selenium não instalado")
    sys.exit(1)


def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-cache")
    
    driver = None
    try:
        print("\n📌 Acessando com force refresh...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.rpa4all.com/")
        
        # Force refresh
        driver.execute_script("window.location.reload(true);")
        time.sleep(4)
        
        # Navegar para IDE
        ide_section = driver.find_element(By.ID, 'ide')
        driver.execute_script("arguments[0].scrollIntoView(true);", ide_section)
        time.sleep(2)
        
        # Verificar
        container = driver.find_element(By.CSS_SELECTOR, 'div.ide-container')
        display = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display", container
        )
        flex_dir = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).flexDirection", container
        )
        
        print(f"\n🔍 Resultado:")
        print(f"  display: {display}")
        print(f"  flex-direction: {flex_dir}")
        
        if display == 'flex' and flex_dir == 'column':
            print(f"\n✅ CORREÇÃO CONFIRMADA - IDE ESPAÇADA CORRETAMENTE!")
            driver.save_screenshot("/tmp/ide_corrected.png")
            print(f"   📸 /tmp/ide_corrected.png")
            return 0
        else:
            print(f"\n❌ Display ainda {display}")
            driver.save_screenshot("/tmp/ide_not_fixed.png")
            return 1
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return 1
    
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
