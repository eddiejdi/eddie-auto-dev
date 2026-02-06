#!/usr/bin/env python3
"""
Detector de elementos achatados/finos na IDE
Encontra elementos com altura reduzida ou problemas de espaçamento
"""

import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    print("❌ Selenium não instalado")
    sys.exit(1)


def setup_driver():
    """Configura driver Chrome"""
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


def analyze_element_dimensions(driver, selector, name):
    """Analisa dimensões de um elemento"""
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if not elements:
            print(f"  ❌ {name}: Não encontrado")
            return None
        
        elem = elements[0]
        
        # Scroll para o elemento se necessário
        driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        time.sleep(0.3)
        
        # Obter dimensões
        rect = elem.get_attribute('style') or ''
        computed_height = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).height", elem
        )
        computed_width = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).width", elem
        )
        min_height = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).minHeight", elem
        )
        overflow = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).overflow", elem
        )
        display = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).display", elem
        )
        
        # Verificar se é "fino"
        try:
            height_px = float(computed_height.replace('px', ''))
            is_thin = height_px < 20
            is_concerning = height_px < 50 and height_px > 0
        except:
            is_thin = False
            is_concerning = False
        
        # Obter estrutura interna
        children_count = len(elem.find_elements(By.XPATH, "./*"))
        
        info = {
            'height': computed_height,
            'width': computed_width,
            'min_height': min_height,
            'overflow': overflow,
            'display': display,
            'children': children_count,
            'is_thin': is_thin,
            'is_concerning': is_concerning
        }
        
        icon = "⚠️" if is_thin else "❓" if is_concerning else "ℹ️"
        print(f"  {icon} {name}:")
        print(f"      height: {computed_height} | min-height: {min_height}")
        print(f"      width: {computed_width} | display: {display}")
        print(f"      overflow: {overflow} | children: {children_count}")
        
        if is_thin:
            print(f"      🚨 ELEMENTO FINO DETECTADO!")
        
        return info
    except Exception as e:
        print(f"  ❌ {name}: Erro - {e}")
        return None


def main():
    print("\n" + "="*70)
    print("🔍 ANÁLISE DE DIMENSÕES - IDE")
    print("="*70)
    
    driver = None
    try:
        print("\n📌 Acessando: https://www.rpa4all.com/")
        driver = setup_driver()
        driver.get("https://www.rpa4all.com/")
        time.sleep(3)
        
        # Navegar para IDE
        print("\n✓ Navegando para seção IDE...")
        ide_section = driver.find_element(By.ID, 'ide')
        driver.execute_script("arguments[0].scrollIntoView(true);", ide_section)
        time.sleep(2)
        
        # Analisar estrutura da IDE
        print("\n" + "="*70)
        print("📐 ESTRUTURA DA IDE")
        print("="*70)
        
        elements_to_analyze = {
            'div.ide-container': 'IDE Container Principal',
            'div.ide-toolbar': 'Toolbar',
            'div.ide-file-tabs': 'File Tabs Section',
            'div.ide-ai-bar': 'AI Bar (com botão Executar Prompt)',
            'div.ide-ai-input': 'AI Input Area',
            'textarea#aiPrompt': 'Textarea do Prompt',
            'div.ide-ai-actions': 'AI Actions (Botões)',
            'button.ai-run': 'Botão Executar Prompt',
            'div.ide-main': 'Main Editor/Output',
            'div.ide-editor-wrapper': 'Editor Wrapper',
            'div#editor': 'Editor Monaco',
            'div.ide-output-wrapper': 'Output Wrapper',
        }
        
        results = {}
        for selector, name in elements_to_analyze.items():
            results[selector] = analyze_element_dimensions(driver, selector, name)
            print()
        
        # Análise de problemas
        print("="*70)
        print("🔴 PROBLEMAS DETECTADOS")
        print("="*70)
        
        thin_elements = [name for selector, name in elements_to_analyze.items() 
                        if results[selector] and results[selector]['is_thin']]
        
        concerning = [name for selector, name in elements_to_analyze.items()
                     if results[selector] and results[selector]['is_concerning']]
        
        if thin_elements:
            print(f"\n🚨 Elementos FINOS detectados:")
            for elem in thin_elements:
                print(f"  - {elem}")
        else:
            print("\n✅ Nenhum elemento fino detectado")
        
        if concerning:
            print(f"\n⚠️  Elementos COM POSSÍVEL PROBLEMA:")
            for elem in concerning:
                print(f"  - {elem}")
        
        # Screenshot
        print("\n✓ Capturando screenshot...")
        driver.save_screenshot("/tmp/ide_dimensions_analysis.png")
        print("  📸 Screenshot: /tmp/ide_dimensions_analysis.png")
        
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
