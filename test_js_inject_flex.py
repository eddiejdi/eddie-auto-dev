#!/usr/bin/env python3
"""Teste injetando flex via JS para confirmar que funciona"""

import sys
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
except ImportError:
    print("❌ Selenium não instalado")
    sys.exit(1)


def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = None
    try:
        print("\n📌 Teste 1: Verificar CSS atual...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.rpa4all.com/")
        time.sleep(3)
        
        container = driver.find_element(By.CSS_SELECTOR, 'div.ide-container')
        display_before = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display", container
        )
        print(f"  Display ANTES: {display_before}")
        
        # Injetar flex via JS
        print("\n📌 Teste 2: Injetando display:flex via JavaScript...")
        driver.execute_script("""
            const container = document.querySelector('.ide-container');
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
        """)
        time.sleep(1)
        
        display_after = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display", container
        )
        flex_dir_after = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).flexDirection", container
        )
        
        print(f"  Display DEPOIS: {display_after}")
        print(f"  Flex Direction: {flex_dir_after}")
        
        if display_after == 'flex':
            print("\n✅ JavaScript pode modificar o estilo corretamente!")
            print("   → CSS do arquivo pode estar sendo sobrescrito por algo")
            driver.save_screenshot("/tmp/ide_js_flex_injected.png")
            return 0
        else:
            print("\n❌ Mesmo JavaScript não conseguiu mudar display")
            return 1
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return 1
    
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
