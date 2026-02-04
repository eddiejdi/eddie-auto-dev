#!/usr/bin/env python3
"""
Script de validação Selenium para endpoints www.rpa4all.com
Testa via navegador real (headless)
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

def setup_driver():
    """Configurar Chrome headless"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--allow-insecure-localhost')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"❌ Erro ao iniciar Chrome: {e}")
        print("   Instale: sudo apt-get install chromium-browser chromium-chromedriver")
        return None

def test_endpoint(driver, url, name, expected_text=None, timeout=10, wait_time=5, screenshot=False):
    """Testar um endpoint específico"""
    print(f"\n🔍 Testando {name}: {url}")
    
    try:
        driver.get(url)
        time.sleep(wait_time)  # Aguardar carregamento (aumentado para SPAs)
        
        # Capturar logs do console
        try:
            logs = driver.get_log('browser')
            errors = [log for log in logs if log['level'] == 'SEVERE']
            if errors:
                print(f"   ⚠️  Erros JavaScript detectados: {len(errors)}")
                for err in errors[:3]:
                    print(f"      - {err['message'][:100]}")
        except:
            pass
        
        # Screenshot opcional
        if screenshot:
            screenshot_path = f"/tmp/selenium_{name.replace(' ', '_')}.png"
            driver.save_screenshot(screenshot_path)
            print(f"   📸 Screenshot salvo: {screenshot_path}")
        
        # Verificar título
        title = driver.title
        print(f"   📄 Título: {title[:80]}")
        
        # Verificar status via page source
        page_source = driver.page_source
        
        # Detectar erro 502
        if '502' in page_source or 'Bad Gateway' in page_source:
            print(f"   ❌ ERRO: Página retornou 502 Bad Gateway")
            return False
        
        # Detectar erro 404
        if '404' in page_source or 'Not Found' in page_source:
            print(f"   ❌ ERRO: Página retornou 404 Not Found")
            return False
        
        # Verificar texto esperado
        if expected_text:
            if expected_text.lower() in page_source.lower():
                print(f"   ✅ Texto esperado encontrado: '{expected_text}'")
            else:
                print(f"   ⚠️  Texto esperado NÃO encontrado: '{expected_text}'")
                print(f"   📝 Primeiros 200 chars: {page_source[:200]}")
        
        # Verificar se há conteúdo
        body = driver.find_element(By.TAG_NAME, "body")
        body_text = body.text.strip()
        
        # Para SPAs, verificar também elementos DOM
        all_elements = driver.find_elements(By.CSS_SELECTOR, "div, main, section, article")
        element_count = len(all_elements)
        
        if len(body_text) > 0:
            print(f"   ✅ Página carregou com conteúdo ({len(body_text)} chars, {element_count} elementos)")
            print(f"   📝 Preview: {body_text[:100]}")
            return True
        elif element_count > 10:
            print(f"   ✅ SPA carregou ({element_count} elementos DOM, mesmo sem texto visível)")
            return True
        else:
            print(f"   ⚠️  Página sem conteúdo visível ({element_count} elementos)")
            return False
            
    except TimeoutException:
        print(f"   ❌ TIMEOUT: Página não carregou em {timeout}s")
        return False
    except WebDriverException as e:
        print(f"   ❌ ERRO WebDriver: {str(e)[:100]}")
        return False
    except Exception as e:
        print(f"   ❌ ERRO: {str(e)[:100]}")
        return False

def main():
    print("=" * 70)
    print("Validação Selenium - www.rpa4all.com")
    print("=" * 70)
    
    # Setup
    driver = setup_driver()
    if not driver:
        return 1
    
    results = {}
    
    try:
        # Teste 1: Root endpoint
        results['Root'] = test_endpoint(
            driver, 
            'https://www.rpa4all.com/',
            'Root endpoint',
            expected_text='OK'
        )
        
        # Teste 2: Grafana
        results['Grafana'] = test_endpoint(
            driver,
            'https://www.rpa4all.com/grafana/',
            'Grafana endpoint',
            expected_text='grafana'
        )
        
        # Teste 3: OpenWebUI (aumentar wait time para SPA)
        results['OpenWebUI'] = test_endpoint(
            driver,
            'https://www.rpa4all.com/openwebui/',
            'OpenWebUI endpoint',
            expected_text='open webui',
            wait_time=8,
            screenshot=True
        )
        
    finally:
        driver.quit()
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES SELENIUM")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    print(f"\n📊 Total: {passed}/{total} endpoints OK")
    
    if passed == total:
        print("\n✅ TODOS OS TESTES SELENIUM PASSARAM!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} testes falharam")
        return 1

if __name__ == "__main__":
    sys.exit(main())
