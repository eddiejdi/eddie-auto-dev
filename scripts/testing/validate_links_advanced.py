#!/usr/bin/env python3
"""
Bot Selenium Avançado para Validação de Links - Landing Page RPA4ALL
Integra técnicas de: test_selenium_endpoints.py, validate_grafana_dashboards_selenium.py, test_site_selenium.py
"""

import sys
import time
import requests
import threading
import socketserver
import http.server
from urllib.parse import urljoin, urlparse
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("❌ Dependências não instaladas. Execute: pip install selenium webdriver-manager requests")
    sys.exit(1)


class AdvancedLinkValidator:
    """Bot Selenium avançado para validação de links"""
    
    def __init__(self, base_url="https://www.rpa4all.com/", headless=True, debug=False):
        self.base_url = base_url
        self.headless = headless
        self.debug = debug
        self.driver = None
        self.results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "internal": [],
            "external": [],
            "errors": []
        }
        
    def setup_driver(self):
        """Setup Chrome driver com configurações avançadas"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless=new')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Adicionar user agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ Chrome driver iniciado com sucesso")
            return True
        except Exception as e:
            print(f"❌ Erro ao iniciar Chrome driver: {e}")
            return False
    
    def load_page(self, url, timeout=15, wait_selector=None):
        """Carrega página com tratamento de timeouts e SPAs"""
        print(f"\n📄 Carregando: {url}")
        
        try:
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(url)
            
            # Aguardar carregamento da página
            time.sleep(2)
            
            # Se especificado, aguardar elemento específico
            if wait_selector:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
                print(f"   ✅ Elemento '{wait_selector}' carregado")
            
            # Aguardar SPAs carregarem
            time.sleep(2)
            
            # Capturar logs do console para erros
            try:
                logs = self.driver.get_log('browser')
                errors = [log for log in logs if log['level'] == 'SEVERE']
                if errors and self.debug:
                    print(f"   ⚠️  Erros JavaScript detectados: {len(errors)}")
                    for err in errors[:2]:
                        print(f"      - {err['message'][:80]}")
            except:
                pass
            
            return True
            
        except TimeoutException:
            print(f"   ❌ Timeout ao carregar página (>{timeout}s)")
            self.results["errors"].append({"url": url, "error": "Timeout no carregamento"})
            return False
        except Exception as e:
            print(f"   ❌ Erro ao carregar: {str(e)[:80]}")
            self.results["errors"].append({"url": url, "error": str(e)})
            return False
    
    def extract_links(self):
        """Extrai todos os links da página com análise robusta"""
        try:
            # Aguardar se houver SPAs renderizando
            time.sleep(1)
            
            # Encontra todos os elementos <a>
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")
            
            links = {
                "internal": [],
                "external": [],
                "anchors": [],
                "email": [],
                "tel": [],
                "other": []
            }
            
            for elem in link_elements:
                try:
                    href = elem.get_attribute("href")
                    text = elem.text.strip()
                    title = elem.get_attribute("title")
                    
                    if not href:
                        continue
                    
                    # Classificar link
                    if href.startswith("mailto:"):
                        links["email"].append({
                            "href": href,
                            "text": text or title or "[email]",
                            "type": "email"
                        })
                    elif href.startswith("tel:"):
                        links["tel"].append({
                            "href": href,
                            "text": text or title or "[tel]",
                            "type": "tel"
                        })
                    elif href.startswith("#"):
                        links["anchors"].append({
                            "href": href,
                            "text": text or title or href,
                            "type": "anchor"
                        })
                    elif href.startswith("http"):
                        if self.base_url.rstrip('/') in href:
                            links["internal"].append({
                                "href": href,
                                "text": text or title or "[sem texto]",
                                "type": "internal"
                            })
                        else:
                            links["external"].append({
                                "href": href,
                                "text": text or title or "[sem texto]",
                                "type": "external"
                            })
                    else:
                        # URL relativa
                        abs_url = urljoin(self.base_url, href)
                        links["internal"].append({
                            "href": abs_url,
                            "text": text or title or "[sem texto]",
                            "type": "internal"
                        })
                
                except Exception as e:
                    if self.debug:
                        print(f"   ⚠️  Erro ao processar link: {e}")
                    continue
            
            return links
            
        except Exception as e:
            print(f"   ❌ Erro ao extrair links: {e}")
            return {}
    
    def validate_link(self, link, link_type="internal"):
        """Valida um link específico com múltiplas estratégias"""
        href = link["href"]
        text = link["text"]
        
        # Validar links de email
        if link_type == "email":
            if href.startswith("mailto:"):
                return {"status": 200, "valid": True, "message": "Email válido"}
            return {"status": 400, "valid": False, "message": "Email inválido"}
        
        # Validar links de tel
        if link_type == "tel":
            if href.startswith("tel:"):
                return {"status": 200, "valid": True, "message": "Telefone válido"}
            return {"status": 400, "valid": False, "message": "Telefone inválido"}
        
        # Validar links de âncora
        if link_type == "anchor":
            anchor = href.lstrip('#')
            try:
                # Tenta encontrar elemento com ID ou data-target
                elem = self.driver.find_element(By.XPATH, f"//*[@id='{anchor}' or @data-target='{anchor}']")
                return {"status": 200, "valid": True, "message": f"Âncora encontrada"}
            except:
                return {"status": 404, "valid": False, "message": "Âncora não encontrada"}
        
        # Validar links HTTP/HTTPS
        try:
            response = requests.head(
                href, 
                timeout=5, 
                allow_redirects=True, 
                verify=False,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            status = response.status_code
            
            if 200 <= status < 400:
                return {"status": status, "valid": True, "message": "OK"}
            else:
                return {"status": status, "valid": False, "message": f"HTTP {status}"}
                
        except requests.Timeout:
            # Tentar com GET se HEAD falhar
            try:
                response = requests.get(
                    href,
                    timeout=5,
                    allow_redirects=True,
                    verify=False,
                    stream=True,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                status = response.status_code
                
                if 200 <= status < 400:
                    return {"status": status, "valid": True, "message": "OK (GET)"}
                else:
                    return {"status": status, "valid": False, "message": f"HTTP {status} (GET)"}
            except Exception as e:
                return {"status": 0, "valid": False, "message": f"Timeout/Erro: {str(e)[:40]}"}
                
        except Exception as e:
            return {"status": 0, "valid": False, "message": f"Erro: {str(e)[:40]}"}
    
    def run_validation(self, url=None):
        """Executa validação completa"""
        if url is None:
            url = self.base_url
        
        print("\n" + "="*90)
        print("🔍 BOT SELENIUM AVANÇADO - VALIDAÇÃO DE LINKS")
        print("="*90)
        print(f"📍 URL Base: {url}")
        
        # Setup driver
        if not self.setup_driver():
            return False
        
        try:
            # Carregar página
            if not self.load_page(url):
                return False
            
            # Screenshot inicial
            self.driver.save_screenshot("links_validation_advanced.png")
            print(f"   📸 Screenshot salvo: links_validation_advanced.png")
            
            # Extrair links
            print(f"\n📊 Extraindo links...")
            links = self.extract_links()
            
            # Contar totais
            total_links = (
                len(links.get("internal", [])) + 
                len(links.get("external", [])) + 
                len(links.get("anchors", [])) + 
                len(links.get("email", [])) + 
                len(links.get("tel", []))
            )
            
            print(f"\n   Total: {total_links} links encontrados")
            print(f"   📍 Internos: {len(links.get('internal', []))}")
            print(f"   🌐 Externos: {len(links.get('external', []))}")
            print(f"   ⚓ Âncoras: {len(links.get('anchors', []))}")
            print(f"   📧 Email: {len(links.get('email', []))}")
            print(f"   ☎️  Telefone: {len(links.get('tel', []))}")
            
            # Validar links por categoria
            print(f"\n{'='*90}")
            
            # Internos
            if links.get("internal"):
                print(f"\n📍 LINKS INTERNOS:")
                for link in links["internal"]:
                    result = self.validate_link(link, "internal")
                    status_icon = "✅" if result["valid"] else "❌"
                    print(f"   {status_icon} {result['status']} | {link['href'][:60]}")
                    print(f"      └─ Texto: {link['text'][:50]}")
                    
                    if result["valid"]:
                        self.results["success"] += 1
                    else:
                        self.results["failed"] += 1
                    self.results["total"] += 1
            
            # Externos
            if links.get("external"):
                print(f"\n🌐 LINKS EXTERNOS:")
                for link in links["external"]:
                    result = self.validate_link(link, "external")
                    status_icon = "✅" if result["valid"] else "❌"
                    domain = urlparse(link['href']).netloc
                    print(f"   {status_icon} {result['status']} | {domain}")
                    print(f"      └─ URL: {link['href'][:60]}")
                    print(f"      └─ Texto: {link['text'][:50]}")
                    
                    if result["valid"]:
                        self.results["success"] += 1
                    else:
                        self.results["failed"] += 1
                    self.results["total"] += 1
            
            # Âncoras
            if links.get("anchors"):
                print(f"\n⚓ LINKS DE ÂNCORA:")
                for link in links["anchors"]:
                    result = self.validate_link(link, "anchor")
                    status_icon = "✅" if result["valid"] else "❌"
                    print(f"   {status_icon} {link['href']} | {result['message']}")
                    print(f"      └─ Texto: {link['text'][:50]}")
                    
                    if result["valid"]:
                        self.results["success"] += 1
                    else:
                        self.results["failed"] += 1
                    self.results["total"] += 1
            
            # Email
            if links.get("email"):
                print(f"\n📧 EMAILS:")
                for link in links["email"]:
                    print(f"   ✅ {link['href']}")
                    print(f"      └─ Texto: {link['text'][:50]}")
                    self.results["success"] += 1
                    self.results["total"] += 1
            
            # Telefone
            if links.get("tel"):
                print(f"\n☎️  TELEFONES:")
                for link in links["tel"]:
                    print(f"   ✅ {link['href']}")
                    print(f"      └─ Texto: {link['text'][:50]}")
                    self.results["success"] += 1
                    self.results["total"] += 1
            
            # Resumo final
            print(f"\n{'='*90}")
            print(f"📈 RESUMO FINAL")
            print(f"{'='*90}")
            print(f"   Total de links: {self.results['total']}")
            print(f"   ✅ Funcionais: {self.results['success']}")
            print(f"   ❌ Com problemas: {self.results['failed']}")
            
            if self.results['total'] > 0:
                taxa = (self.results['success'] / self.results['total']) * 100
                print(f"   Taxa de sucesso: {taxa:.1f}%")
            
            if self.results['errors']:
                print(f"\n⚠️  Erros capturados: {len(self.results['errors'])}")
                for err in self.results['errors'][:3]:
                    print(f"   • {err['url'][:50]}: {err['error'][:50]}")
            
            status_final = "✅ TODOS OS LINKS OK" if self.results['failed'] == 0 else "⚠️  ALGUNS LINKS COM PROBLEMA"
            print(f"\n{status_final}")
            print(f"{'='*90}")
            
            return self.results['failed'] == 0
            
        finally:
            if self.driver:
                self.driver.quit()
                print("\n✅ Driver encerrado")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.rpa4all.com/"
    debug = "--debug" in sys.argv
    
    validator = AdvancedLinkValidator(base_url=url, debug=debug)
    success = validator.run_validation(url)
    
    sys.exit(0 if success else 1)
