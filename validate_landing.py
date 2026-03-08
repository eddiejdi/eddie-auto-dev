#!/usr/bin/env python3
"""Validação da landing page RPA4ALL com Selenium"""

import sys
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import time
except ImportError:
    print("❌ Selenium não instalado. Execute: pip install selenium")
    sys.exit(1)

def validate_landing_page(url="http://localhost:8001"):
    """Valida elementos da landing page"""
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"❌ Erro ao iniciar ChromeDriver: {e}")
        print("💡 Instale: sudo apt install chromium-browser chromium-chromedriver")
        return False
    
    try:
        print(f"🔍 Testando {url}")
        driver.get(url)
        time.sleep(3)  # Aguarda carregamento
        
        # Valida título
        title = driver.title
        print(f"\n📄 Título: {title}")
        assert "RPA4ALL" in title, f"Título incorreto: {title}"
        print("✅ Título OK")
        
        # Define elementos a validar
        elements = {
            "Logo R4": ("xpath", "//div[@class='logo' and text()='R4']"),
            "Brand RPA4ALL": ("xpath", "//h1[text()='RPA4ALL']"),
            "Tagline": ("xpath", "//*[contains(text(), 'Automação inteligente')]"),
            "Botão Open WebUI": ("xpath", "//a[contains(text(), 'Abrir Open WebUI')]"),
            "Botão Grafana": ("xpath", "//a[contains(text(), 'Ver Observabilidade')]"),
            "Tab Soluções": ("xpath", "//button[@data-target='solutions']"),
            "Tab Projetos": ("xpath", "//button[@data-target='projects']"),
            "Tab Plataformas": ("xpath", "//button[@data-target='platforms']"),
            "Seção Solutions": ("xpath", "//section[@id='solutions']//h2[text()='Soluções']"),
            "Card Operações": ("xpath", "//h3[contains(text(), 'Operações inteligentes')]"),
            "Card Observabilidade": ("xpath", "//h3[contains(text(), 'Observabilidade executiva')]"),
            "Seção Projetos": ("xpath", "//section[@id='projects']//h2[contains(text(), 'destaque')]"),
            "Seção Plataformas": ("xpath", "//section[@id='platforms']//h2[contains(text(), 'Plataformas')]"),
            "Link Open WebUI": ("xpath", "//a[@href='https://www.rpa4all.com/openwebui/']"),
            "Link Grafana": ("xpath", "//a[@href='https://www.rpa4all.com/grafana/']"),
            "Link GitHub Repo": ("xpath", "//a[@href='https://github.com/eddiejdi/shared-auto-dev']"),
        }
        
        found = []
        missing = []
        
        print("\n🧪 Validando elementos...")
        for name, (by_type, locator) in elements.items():
            try:
                if by_type == "xpath":
                    element = driver.find_element(By.XPATH, locator)
                else:
                    element = driver.find_element(By.CSS_SELECTOR, locator)
                found.append(name)
                print(f"  ✅ {name}")
            except Exception as e:
                missing.append(name)
                print(f"  ❌ {name} - {str(e)[:50]}")
        
        # Screenshot
        screenshot_path = "landing_validation.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n📸 Screenshot salvo: {screenshot_path}")
        
        # Verifica links
        links = driver.find_elements(By.TAG_NAME, "a")
        external_links = [l for l in links if l.get_attribute("href") and "http" in l.get_attribute("href")]
        print(f"\n🔗 Links externos encontrados: {len(external_links)}")
        for link in external_links[:8]:
            href = link.get_attribute("href")
            text = link.text.strip()[:30]
            print(f"   • {text} → {href}")
        
        # Resumo
        print(f"\n{'='*60}")
        print(f"📊 RESUMO DA VALIDAÇÃO")
        print(f"{'='*60}")
        print(f"   Total de elementos testados: {len(elements)}")
        print(f"   ✅ Encontrados: {len(found)}")
        print(f"   ❌ Não encontrados: {len(missing)}")
        print(f"   Taxa de sucesso: {len(found)/len(elements)*100:.1f}%")
        
        if missing:
            print(f"\n⚠️  Elementos faltando:")
            for m in missing:
                print(f"   • {m}")
        
        success = len(missing) == 0
        print(f"\n{'✅ VALIDAÇÃO PASSOU' if success else '⚠️  VALIDAÇÃO FALHOU'}")
        print(f"{'='*60}")
        
        return success
        
    finally:
        driver.quit()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    success = validate_landing_page(url)
    sys.exit(0 if success else 1)
