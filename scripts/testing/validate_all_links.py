#!/usr/bin/env python3
"""Validação completa de todos os links da landing page com Selenium"""

import sys
import time

import requests

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
except ImportError:
    print("❌ Selenium não instalado. Execute: pip install selenium requests")
    sys.exit(1)

def validate_all_links(base_url="https://www.rpa4all.com/"):
    """Valida todos os links da página"""
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"❌ Erro ao iniciar ChromeDriver: {e}")
        return False
    
    try:
        print(f"🔍 Acessando {base_url}")
        driver.get(base_url)
        time.sleep(3)
        
        # Encontra todos os links
        link_elements = driver.find_elements(By.TAG_NAME, "a")
        links = []
        
        for elem in link_elements:
            href = elem.get_attribute("href")
            text = elem.text.strip()
            if href:
                links.append({"href": href, "text": text, "element": elem})
        
        print(f"\n📊 Total de links encontrados: {len(links)}\n")
        
        # Classifica links por tipo
        internal_links = [l for l in links if base_url.rstrip('/') in l['href']]
        external_links = [l for l in links if 'http' in l['href'] and base_url.rstrip('/') not in l['href']]
        anchor_links = [l for l in links if l['href'].startswith('#')]
        
        print(f"   📍 Links internos: {len(internal_links)}")
        print(f"   🌐 Links externos: {len(external_links)}")
        print(f"   ⚓ Links de âncora: {len(anchor_links)}")
        print(f"\n{'='*80}\n")
        
        # Validação de links internos
        print("🔗 LINKS INTERNOS:")
        print("-" * 80)
        internal_ok = 0
        internal_fail = []
        
        for link in internal_links:
            href = link['href']
            text = link['text'][:40] if link['text'] else '[sem texto]'
            
            try:
                response = requests.head(href, timeout=5, allow_redirects=True, verify=False)
                status = response.status_code
                
                if 200 <= status < 400:
                    print(f"  ✅ {status} | {href}")
                    print(f"     └─ Texto: {text}")
                    internal_ok += 1
                else:
                    print(f"  ⚠️  {status} | {href}")
                    print(f"     └─ Texto: {text}")
                    internal_fail.append((href, status, text))
            except Exception as e:
                print(f"  ❌ ERRO | {href}")
                print(f"     └─ {str(e)[:50]}")
                internal_fail.append((href, "ERRO", text))
        
        print(f"\n   Resultado: {internal_ok}/{len(internal_links)} OK\n")
        
        # Validação de links externos
        print("🌐 LINKS EXTERNOS:")
        print("-" * 80)
        external_ok = 0
        external_fail = []
        
        for link in external_links:
            href = link['href']
            text = link['text'][:40] if link['text'] else '[sem texto]'
            
            # Extrai o domínio para display
            from urllib.parse import urlparse
            domain = urlparse(href).netloc
            
            try:
                response = requests.head(href, timeout=5, allow_redirects=True, verify=False)
                status = response.status_code
                
                if 200 <= status < 400:
                    print(f"  ✅ {status} | {domain}")
                    print(f"     └─ URL: {href}")
                    print(f"     └─ Texto: {text}")
                    external_ok += 1
                else:
                    print(f"  ⚠️  {status} | {domain}")
                    print(f"     └─ URL: {href}")
                    external_fail.append((href, status, text))
            except Exception as e:
                print(f"  ❌ ERRO | {domain}")
                print(f"     └─ URL: {href}")
                print(f"     └─ Erro: {str(e)[:50]}")
                external_fail.append((href, "ERRO", text))
        
        print(f"\n   Resultado: {external_ok}/{len(external_links)} OK\n")
        
        # Validação de links de âncora (verificar se existem no DOM)
        print("⚓ LINKS DE ÂNCORA:")
        print("-" * 80)
        anchor_ok = 0
        anchor_fail = []
        
        for link in anchor_links:
            anchor = link['href'].lstrip('#')
            text = link['text'][:40] if link['text'] else '[sem texto]'
            
            try:
                # Verifica se o elemento com ID existe
                element = driver.find_element(By.ID, anchor)
                print(f"  ✅ #{anchor}")
                print(f"     └─ Texto: {text}")
                anchor_ok += 1
            except:
                # Tenta com xpath também (seções com id ou data-target)
                try:
                    element = driver.find_element(By.XPATH, f"//*[@id='{anchor}' or @data-target='{anchor}']")
                    print(f"  ✅ #{anchor}")
                    print(f"     └─ Texto: {text}")
                    anchor_ok += 1
                except:
                    print(f"  ❌ #{anchor} (elemento não encontrado)")
                    print(f"     └─ Texto: {text}")
                    anchor_fail.append((anchor, text))
        
        print(f"\n   Resultado: {anchor_ok}/{len(anchor_links)} OK\n")
        
        # Relatório final
        print("=" * 80)
        print("📈 RESUMO FINAL")
        print("=" * 80)
        
        total_links = len(internal_links) + len(external_links) + len(anchor_links)
        total_ok = internal_ok + external_ok + anchor_ok
        total_fail = len(internal_fail) + len(external_fail) + len(anchor_fail)
        
        print(f"\n  Total de links: {total_links}")
        print(f"  ✅ Funcionais: {total_ok}")
        print(f"  ❌ Com problemas: {total_fail}")
        print(f"  Taxa de sucesso: {total_ok/total_links*100:.1f}%")
        
        if internal_fail:
            print("\n⚠️  Links internos com problema:")
            for url, status, text in internal_fail:
                print(f"   • {url} ({status})")
        
        if external_fail:
            print("\n⚠️  Links externos com problema:")
            for url, status, text in external_fail:
                print(f"   • {url} ({status})")
        
        if anchor_fail:
            print("\n⚠️  Âncoras não encontradas:")
            for anchor, text in anchor_fail:
                print(f"   • #{anchor}")
        
        success = total_fail == 0
        print(f"\n{'✅ TODOS OS LINKS OK' if success else '⚠️  ALGUNS LINKS COM PROBLEMA'}")
        print("=" * 80)
        
        # Screenshot
        driver.save_screenshot("links_validation.png")
        print("\n📸 Screenshot: links_validation.png")
        
        return success
        
    finally:
        driver.quit()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.rpa4all.com/"
    success = validate_all_links(url)
    sys.exit(0 if success else 1)
