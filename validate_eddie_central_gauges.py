#!/usr/bin/env python3
"""
Validação detalhada de todos os gauges do dashboard Eddie Central
Usa Selenium para extrair e validar cada gauge individualmente
"""

import time
import sys
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configurações
GRAFANA_URL = "https://grafana.rpa4all.com/d/eddie-central/eddie-auto-dev-e28094-central"
GRAFANA_PARAMS = "?orgId=1&from=now-6h&to=now&timezone=browser&refresh=30s"
FULL_URL = f"{GRAFANA_URL}{GRAFANA_PARAMS}"
GRAFANA_BASE = "https://grafana.rpa4all.com"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "Eddie@2026"

class EddieCentralGaugeValidator:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard": "Eddie Central",
            "url": FULL_URL,
            "gauges": [],
            "summary": {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "errors": 0
            }
        }
    
    def setup_chrome(self):
        """Configura Chrome com Selenium"""
        print("🔧 Configurando Chrome...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            print("✅ Chrome configurado com sucesso")
            return True
        except Exception as e:
            print(f"❌ Erro ao configurar Chrome: {e}")
            return False
    
    def login(self):
        """Faz login no Grafana"""
        print("\n🔐 Fazendo login no Grafana...")
        
        try:
            # Ir para página de login
            login_url = f"{GRAFANA_BASE}/login"
            self.driver.get(login_url)
            time.sleep(2)
            
            # Aguardar campos de login
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "user"))
            )
            
            # Preencher credenciais
            username_field.clear()
            username_field.send_keys(GRAFANA_USER)
            
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(GRAFANA_PASSWORD)
            
            # Clicar no botão de login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Aguardar redirecionamento
            time.sleep(3)
            
            # Verificar se login foi bem-sucedido
            if "/login" not in self.driver.current_url:
                print("✅ Login bem-sucedido")
                return True
            else:
                print(f"❌ Falha no login - URL atual: {self.driver.current_url}")
                return False
        
        except Exception as e:
            print(f"❌ Erro durante login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_dashboard(self):
        """Carrega o dashboard Eddie Central"""
        print(f"\n📊 Carregando dashboard: {FULL_URL}")
        
        try:
            self.driver.get(FULL_URL)
            
            # Aguardar carregamento de painéis
            print("⏳ Aguardando carregamento dos painéis...")
            time.sleep(10)  # Aguardar render completo
            
            # Debug: capturar screenshot
            screenshot_path = "/tmp/eddie_central_screenshot.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"📸 Screenshot salvo em: {screenshot_path}")
            
            # Debug: capturar título da página
            page_title = self.driver.title
            print(f"📄 Título da página: {page_title}")
            
            # Debug: verificar URL atual
            current_url = self.driver.current_url
            print(f"🔗 URL atual: {current_url}")
            
            # Verificar se dashboard carregou
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='dashboard-scene']"))
                )
                print("✅ Dashboard carregado com sucesso")
                return True
            except:
                # Fallback: verificar por painéis genéricos
                print("⏳ Tentando seletores alternativos...")
                
                # Testar múltiplos seletores
                test_selectors = [
                    ".panel-container",
                    "[class*='panel']",
                    "[data-panelid]",
                    "[class*='Panel']",
                    ".react-grid-item"
                ]
                
                for selector in test_selectors:
                    panels = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if panels:
                        print(f"✅ Dashboard carregado ({len(panels)} painéis detectados com {selector})")
                        return True
                
                # Debug: imprimir conteúdo da página
                page_source = self.driver.page_source[:500]
                print(f"📝 Início do HTML: {page_source}")
                
                print("❌ Dashboard não carregou corretamente")
                return False
        
        except Exception as e:
            print(f"❌ Erro ao carregar dashboard: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_all_gauges(self):
        """Extrai todos os gauges do dashboard"""
        print("\n🔍 Buscando todos os gauges...")
        
        # Seletores para diferentes tipos de gauges/stats no Grafana
        selectors = [
            "[data-viz-panel-key*='gauge']",
            "[data-viz-panel-key*='stat']",
            ".panel-container[aria-label*='gauge' i]",
            ".panel-container[aria-label*='stat' i]",
            "[class*='Panel_panel'][class*='gauge']",
            "[class*='Panel_panel'][class*='stat']",
            # Seletores mais genéricos
            ".panel-container",
            "[data-panelid]"
        ]
        
        all_panels = []
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"   Encontrados {len(elements)} elementos com seletor: {selector}")
                    all_panels.extend(elements)
            except Exception as e:
                print(f"   ⚠️ Erro com seletor {selector}: {e}")
        
        # Remover duplicatas (mesmo elemento em diferentes seletores)
        unique_panels = list({panel.id: panel for panel in all_panels}.values())
        
        print(f"✅ Total de {len(unique_panels)} painéis únicos encontrados")
        return unique_panels
    
    def validate_gauge(self, panel_element, index):
        """Valida um gauge individual"""
        gauge_info = {
            "index": index,
            "title": "Unknown",
            "type": "Unknown",
            "value": None,
            "status": "UNKNOWN",
            "issues": []
        }
        
        try:
            # Extrair título do painel
            try:
                title_elem = panel_element.find_element(By.CSS_SELECTOR, 
                    "[class*='panel-title'], h6, [data-testid='panel-header-title']")
                gauge_info["title"] = title_elem.text.strip()
            except:
                # Tentar via aria-label
                try:
                    aria_label = panel_element.get_attribute("aria-label")
                    if aria_label:
                        gauge_info["title"] = aria_label
                except:
                    gauge_info["title"] = f"Panel {index}"
            
            # Detectar tipo de painel
            class_name = panel_element.get_attribute("class") or ""
            data_viz = panel_element.get_attribute("data-viz-panel-key") or ""
            
            if "gauge" in class_name.lower() or "gauge" in data_viz.lower():
                gauge_info["type"] = "Gauge"
            elif "stat" in class_name.lower() or "stat" in data_viz.lower():
                gauge_info["type"] = "Stat"
            else:
                gauge_info["type"] = "Panel"
            
            # Extrair valor exibido (tentar múltiplos seletores)
            value_selectors = [
                "[class*='BigValue']",
                "[class*='bigValue']",
                "[class*='singlestat']",
                ".graph-legend-value",
                "[class*='value']",
                "text",  # Para SVG
                "span"
            ]
            
            value_found = False
            for selector in value_selectors:
                try:
                    value_elems = panel_element.find_elements(By.CSS_SELECTOR, selector)
                    for val_elem in value_elems:
                        val_text = val_elem.text.strip()
                        if val_text and len(val_text) < 50:  # Evitar textos muito longos
                            gauge_info["value"] = val_text
                            value_found = True
                            break
                    if value_found:
                        break
                except:
                    continue
            
            if not value_found:
                gauge_info["issues"].append("Valor não encontrado")
            
            # Verificar por erros visuais
            error_indicators = [
                ".alert-error",
                "[class*='error']",
                ".panel-info-card--error",
                "[data-testid='panel-status-error']"
            ]
            
            for error_sel in error_indicators:
                try:
                    errors = panel_element.find_elements(By.CSS_SELECTOR, error_sel)
                    if errors:
                        gauge_info["issues"].append(f"Erro detectado: {errors[0].text}")
                except:
                    continue
            
            # Verificar valores inválidos
            if gauge_info["value"]:
                val_lower = gauge_info["value"].lower()
                invalid_markers = ["nan", "null", "undefined", "n/a", "error", "no data"]
                
                for marker in invalid_markers:
                    if marker in val_lower:
                        gauge_info["issues"].append(f"Valor inválido: {gauge_info['value']}")
                        break
            
            # Determinar status final
            if gauge_info["issues"]:
                gauge_info["status"] = "INVALID"
            elif gauge_info["value"]:
                gauge_info["status"] = "VALID"
            else:
                gauge_info["status"] = "UNKNOWN"
            
            return gauge_info
        
        except Exception as e:
            gauge_info["status"] = "ERROR"
            gauge_info["issues"].append(f"Erro durante validação: {str(e)}")
            return gauge_info
    
    def validate_all_gauges(self, panels):
        """Valida todos os gauges encontrados"""
        print(f"\n📋 Validando {len(panels)} painéis...\n")
        
        for idx, panel in enumerate(panels, 1):
            try:
                # Scroll até o painel para garantir que está visível
                self.driver.execute_script("arguments[0].scrollIntoView(true);", panel)
                time.sleep(0.5)
                
                gauge_info = self.validate_gauge(panel, idx)
                self.results["gauges"].append(gauge_info)
                
                # Print resultado
                status_emoji = {
                    "VALID": "✅",
                    "INVALID": "❌",
                    "ERROR": "🔴",
                    "UNKNOWN": "❓"
                }
                
                emoji = status_emoji.get(gauge_info["status"], "❓")
                print(f"{emoji} [{idx}/{len(panels)}] {gauge_info['title']}")
                print(f"    Tipo: {gauge_info['type']}")
                print(f"    Valor: {gauge_info['value']}")
                
                if gauge_info["issues"]:
                    print(f"    Problemas:")
                    for issue in gauge_info["issues"]:
                        print(f"      • {issue}")
                print()
                
                # Atualizar sumário
                self.results["summary"]["total"] += 1
                if gauge_info["status"] == "VALID":
                    self.results["summary"]["valid"] += 1
                elif gauge_info["status"] == "INVALID":
                    self.results["summary"]["invalid"] += 1
                elif gauge_info["status"] == "ERROR":
                    self.results["summary"]["errors"] += 1
            
            except Exception as e:
                print(f"❌ Erro ao validar painel {idx}: {e}\n")
                self.results["summary"]["errors"] += 1
    
    def generate_report(self):
        """Gera relatório final"""
        print("\n" + "=" * 80)
        print("📊 RELATÓRIO DE VALIDAÇÃO - EDDIE CENTRAL DASHBOARD")
        print("=" * 80)
        
        summary = self.results["summary"]
        print(f"\n📈 RESUMO:")
        print(f"   Total de painéis: {summary['total']}")
        print(f"   ✅ Válidos: {summary['valid']}")
        print(f"   ❌ Inválidos: {summary['invalid']}")
        print(f"   🔴 Erros: {summary['errors']}")
        
        # Taxa de sucesso
        if summary['total'] > 0:
            success_rate = (summary['valid'] / summary['total']) * 100
            print(f"\n   Taxa de sucesso: {success_rate:.1f}%")
        
        # Listar painéis com problemas
        invalid_gauges = [g for g in self.results["gauges"] if g["status"] in ["INVALID", "ERROR"]]
        
        if invalid_gauges:
            print(f"\n❌ PAINÉIS COM PROBLEMAS ({len(invalid_gauges)}):")
            for gauge in invalid_gauges:
                print(f"\n   • {gauge['title']} (Tipo: {gauge['type']})")
                print(f"     Valor: {gauge['value']}")
                print(f"     Status: {gauge['status']}")
                if gauge['issues']:
                    for issue in gauge['issues']:
                        print(f"       - {issue}")
        
        print("\n" + "=" * 80)
        
        # Salvar resultado em JSON
        output_file = "/tmp/eddie_central_validation.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Relatório detalhado salvo em: {output_file}")
        
        return summary['invalid'] == 0 and summary['errors'] == 0
    
    def run(self):
        """Executa validação completa"""
        print("=" * 80)
        print("🚀 VALIDAÇÃO DE GAUGES - EDDIE CENTRAL DASHBOARD")
        print("=" * 80)
        print(f"🕐 Timestamp: {self.results['timestamp']}")
        print(f"🔗 URL: {FULL_URL}")
        
        try:
            # Setup Chrome
            if not self.setup_chrome():
                return False
            
            # Fazer login
            if not self.login():
                return False
            
            # Carregar dashboard
            if not self.load_dashboard():
                return False
            
            # Extrair gauges
            panels = self.extract_all_gauges()
            if not panels:
                print("❌ Nenhum painel encontrado no dashboard!")
                return False
            
            # Validar gauges
            self.validate_all_gauges(panels)
            
            # Gerar relatório
            success = self.generate_report()
            
            return success
        
        except Exception as e:
            print(f"\n❌ Erro crítico durante validação: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.driver:
                print("\n🔒 Fechando navegador...")
                self.driver.quit()


if __name__ == "__main__":
    validator = EddieCentralGaugeValidator()
    success = validator.run()
    
    sys.exit(0 if success else 1)
