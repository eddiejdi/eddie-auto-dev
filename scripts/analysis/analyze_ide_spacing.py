#!/usr/bin/env python3
"""
Análise detalhada de espaçamento e gaps na IDE
Procura por elementos comprimidos ou com gaps incorretos
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


def get_detailed_styles(driver, selector):
    """Obtém estilos detalhados de um elemento"""
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if not elements:
            return None
        
        elem = elements[0]
        
        # CSS properties importantes
        properties = [
            'height', 'width', 'minHeight', 'maxHeight',
            'padding', 'margin', 'gap',
            'display', 'gridTemplateColumns', 'gridTemplateRows',
            'flexDirection', 'justifyContent', 'alignItems',
            'overflow', 'overflowX', 'overflowY',
            'fontSize', 'lineHeight', 'borderRadius',
            'backgroundColor', 'border'
        ]
        
        styles = {}
        for prop in properties:
            styles[prop] = driver.execute_script(
                f"return window.getComputedStyle(arguments[0]).{prop}", elem
            )
        
        return styles
    except:
        return None


def main():
    print("\n" + "="*70)
    print("🔍 ANÁLISE DETALHADA DE ESPAÇAMENTO - IDE")
    print("="*70)
    
    driver = None
    try:
        print("\n📌 Acessando: https://www.rpa4all.com/")
        driver = setup_driver()
        driver.get("https://www.rpa4all.com/")
        time.sleep(3)
        
        # Navegar para IDE
        print("✓ Navegando para IDE...")
        ide_section = driver.find_element(By.ID, 'ide')
        driver.execute_script("arguments[0].scrollIntoView(true);", ide_section)
        time.sleep(2)
        
        # Analisar elementos chave
        print("\n" + "="*70)
        print("📋 ANÁLISE DE ESPAÇAMENTO E LAYOUT")
        print("="*70)
        
        sections = {
            'div.ide-ai-bar': 'AI Bar (com Executar Prompt)',
            'div.ide-ai-actions': 'AI Actions (Botões)',
            'button.ai-run': 'Botão Executar Prompt',
            'div.ide-main': 'Main (Editor + Output)',
            'div.ide-output-wrapper': 'Output Wrapper',
        }
        
        for selector, name in sections.items():
            print(f"\n🔹 {name} ({selector})")
            styles = get_detailed_styles(driver, selector)
            
            if not styles:
                print("  ❌ Não encontrado")
                continue
            
            # Mostrar informações relevantes
            print(f"  Display: {styles['display']}")
            print(f"  Height: {styles['height']} | MinHeight: {styles['minHeight']}")
            print(f"  Padding: {styles['padding']}")
            print(f"  Margin: {styles['margin']}")
            print(f"  Gap: {styles['gap']}")
            
            if styles['display'] == 'grid':
                print(f"  Grid Columns: {styles['gridTemplateColumns']}")
                print(f"  Grid Rows: {styles['gridTemplateRows']}")
            elif styles['display'] == 'flex':
                print(f"  Flex Direction: {styles['flexDirection']}")
                print(f"  Justify Content: {styles['justifyContent']}")
                print(f"  Align Items: {styles['alignItems']}")
            
            print(f"  Overflow: {styles['overflow']}")
        
        # Verificar a ordem visual dos elementos
        print("\n" + "="*70)
        print("🎯 VERIFICAÇÃO DE ORDEM VISUAL")
        print("="*70)
        
        # Estrutura esperada:
        # 1. ide-toolbar
        # 2. ide-ai-bar (label, textarea, botão)
        # 3. ide-main (editor + output)
        
        toolbar = driver.find_elements(By.CSS_SELECTOR, 'div.ide-toolbar')
        ai_bar = driver.find_elements(By.CSS_SELECTOR, 'div.ide-ai-bar')
        main_area = driver.find_elements(By.CSS_SELECTOR, 'div.ide-main')
        
        print(f"\n✓ Toolbar: {'✅ Encontrado' if toolbar else '❌ Não encontrado'}")
        print(f"✓ AI Bar: {'✅ Encontrado' if ai_bar else '❌ Não encontrado'}")
        print(f"✓ Main Area: {'✅ Encontrado' if main_area else '❌ Não encontrado'}")
        
        # Verificar se há espaço entre elementos
        if toolbar and ai_bar:
            toolbar_elem = toolbar[0]
            ai_bar_elem = ai_bar[0]
            
            toolbar_rect = driver.execute_script(
                "return arguments[0].getBoundingClientRect()", toolbar_elem
            )
            ai_rect = driver.execute_script(
                "return arguments[0].getBoundingClientRect()", ai_bar_elem
            )
            
            gap = ai_rect['top'] - toolbar_rect['bottom']
            print(f"\n  Espaço entre Toolbar e AI Bar: {gap}px")
            if gap < 0:
                print("    🚨 PROBLEMA: Elementos se sobrepõem!")
            elif gap == 0:
                print("    ⚠️  AVISO: Sem gap entre elementos")
        
        if ai_bar and main_area:
            ai_bar_elem = ai_bar[0]
            main_elem = main_area[0]
            
            ai_rect = driver.execute_script(
                "return arguments[0].getBoundingClientRect()", ai_bar_elem
            )
            main_rect = driver.execute_script(
                "return arguments[0].getBoundingClientRect()", main_elem
            )
            
            gap = main_rect['top'] - ai_rect['bottom']
            print(f"  Espaço entre AI Bar e Main: {gap}px")
            if gap < 0:
                print("    🚨 PROBLEMA: AI Bar e Main se sobrepõem!")
            elif gap == 0:
                print("    ⚠️  AVISO: Sem gap entre elementos")
        
        # Capturar screenshot
        print("\n✓ Capturando screenshot...")
        driver.save_screenshot("/tmp/ide_spacing_analysis.png")
        print("  📸 Screenshot: /tmp/ide_spacing_analysis.png")
        
        return 0
    
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
