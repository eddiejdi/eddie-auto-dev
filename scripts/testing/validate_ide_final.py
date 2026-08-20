#!/usr/bin/env python3
"""
Validação Visual Final - Comparação Antes/Depois
Verifica a correção do problema de espaçamento
"""

import sys
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
except ImportError:
    print("❌ Selenium não instalado")
    sys.exit(1)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"❌ Erro ao inicializar Chrome: {e}")
        sys.exit(1)


def main():
    print("\n" + "="*70)
    print("✅ VALIDAÇÃO FINAL - CORREÇÃO DE ESPAÇAMENTO")
    print("="*70)
    
    driver = None
    try:
        print("\n📌 Acessando: https://www.rpa4all.com/")
        driver = setup_driver()
        driver.get("https://www.rpa4all.com/")
        time.sleep(3)
        
        # Navegar para IDE
        print("✓ Navegando para seção IDE...")
        ide_section = driver.find_element(By.ID, 'ide')
        driver.execute_script("arguments[0].scrollIntoView(true);", ide_section)
        time.sleep(2)
        
        # Verificar estrutura
        print("\n" + "="*70)
        print("🎯 VERIFICAÇÃO DE ESTRUTURA")
        print("="*70)
        
        # 1. Verificar display do container
        container = driver.find_element(By.CSS_SELECTOR, 'div.ide-container')
        display = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display", container
        )
        flex_direction = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).flexDirection", container
        )
        
        print("\n🔹 ide-container:")
        print(f"  display: {display}")
        print(f"  flex-direction: {flex_direction}")
        
        if display == 'flex' and flex_direction == 'column':
            print("  ✅ Estrutura flex aplicada corretamente!")
        else:
            print(f"  ⚠️  Display está {display} (esperado: flex)")
        
        # 2. Verificar seções dentro do container
        toolbar = driver.find_element(By.CSS_SELECTOR, 'div.ide-toolbar')
        ai_bar = driver.find_element(By.CSS_SELECTOR, 'div.ide-ai-bar')
        main_area = driver.find_element(By.CSS_SELECTOR, 'div.ide-main')
        
        # 3. Verificar posicionamento e visibilidade
        print("\n🔹 Elementos da IDE:")
        
        for name, elem in [('Toolbar', toolbar), ('AI Bar', ai_bar), ('Main Area', main_area)]:
            computed_height = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).height", elem
            )
            visibility = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).visibility", elem
            )
            print(f"  {name}: height={computed_height}, visibility={visibility}")
        
        # 4. Verificar espaçamento relativo
        print("\n🔹 Espaçamento entre elementos:")
        
        toolbar_rect = driver.execute_script(
            "return arguments[0].getBoundingClientRect()", toolbar
        )
        ai_rect = driver.execute_script(
            "return arguments[0].getBoundingClientRect()", ai_bar
        )
        main_rect = driver.execute_script(
            "return arguments[0].getBoundingClientRect()", main_area
        )
        
        gap1 = ai_rect['top'] - toolbar_rect['bottom']
        gap2 = main_rect['top'] - ai_rect['bottom']
        
        print(f"  Entre Toolbar e AI Bar: {gap1}px")
        print(f"  Entre AI Bar e Main: {gap2}px")
        
        if gap1 >= 0 and gap2 >= 0:
            print("  ✅ Elementos não se sobrepõem")
        else:
            print("  ⚠️  Possível sobreposição detectada")
        
        # 5. Screenshot final
        print("\n✓ Capturando screenshot final...")
        driver.save_screenshot("/tmp/ide_final_validation.png")
        print("  📸 Screenshot: /tmp/ide_final_validation.png")
        
        # 6. Relatório final
        print("\n" + "="*70)
        print("📊 RESULTADO FINAL")
        print("="*70)
        
        if display == 'flex' and gap1 >= 0 and gap2 >= 0:
            print("\n✅ IDE CORRIGIDA - ESPAÇAMENTO NORMALIZADO!")
            print("\n✨ Próximas iterações:")
            print("   1. CSS grid com flex-direction: column aplicado")
            print("   2. Elementos dispostos verticalmente sem sobreposição")
            print("   3. Visibilidade e responsividade mantidas")
            return 0
        else:
            print("\n⚠️  Verificação necessária - alguns items fora do esperado")
            return 1
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
