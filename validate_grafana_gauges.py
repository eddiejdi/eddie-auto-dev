#!/usr/bin/env python3
"""
Validação Selenium para gauges do dashboard Eddie WhatsApp no Grafana
Verifica painéis tipo 'gauge' e 'stat' para conteúdos inválidos
"""

import time
import json
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

GRAFANA_URL = "http://192.168.15.2:3002/grafana"
DASHBOARD_UID = "eddie-whatsapp-training"
DASHBOARD_URL = f"{GRAFANA_URL}/d/{DASHBOARD_UID}"
CREDENTIALS = {"username": "admin", "password": "Eddie@2026"}

class GrafanaGaugeValidator:
    """Validador de gauges do Grafana"""
    
    def __init__(self):
        self.driver = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard": DASHBOARD_UID,
            "gauges": [],
            "stats": [],
            "errors": [],
            "summary": {}
        }
    
    def setup_driver(self):
        """Configurar Chrome headless"""
        print("🚀 Inicializando driver Chrome...")
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280,720')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-resources')
        chrome_options.add_argument('--disable-sync')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(60)
            return True
        except Exception as e:
            print(f"❌ Erro ao iniciar Chrome: {e}")
            self.results["errors"].append(f"Driver init: {str(e)}")
            return False
    
    def login(self):
        """Fazer login no Grafana"""
        print("🔐 Fazendo login...")
        try:
            self.driver.get(GRAFANA_URL)
            time.sleep(2)
            
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_all_elements_located((By.NAME, "user"))
            )
            
            username_field = self.driver.find_element(By.NAME, "user")
            password_field = self.driver.find_element(By.NAME, "password")
            
            username_field.send_keys(CREDENTIALS["username"])
            password_field.send_keys(CREDENTIALS["password"])
            
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Aguardar redirecionamento
            time.sleep(5)
            WebDriverWait(self.driver, 20).until(
                EC.url_changes(GRAFANA_URL)
            )
            
            print("✅ Login realizado")
            return True
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            self.results["errors"].append(f"Login failed: {str(e)}")
            return False
    
    def navigate_to_dashboard(self):
        """Navegar para o dashboard"""
        print(f"📊 Acessando dashboard: {DASHBOARD_UID}")
        try:
            self.driver.get(DASHBOARD_URL)
            
            # Aguardar que o dashboard carregue
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "panel-content"))
            )
            
            time.sleep(3)  # Aguardar renderização dos painéis
            print(f"✅ Dashboard carregado: {DASHBOARD_URL}")
            print(f"   URL atual: {self.driver.current_url}")
            return True
        except TimeoutException as e:
            print(f"❌ Timeout ao carregar dashboard: {e}")
            self.results["errors"].append(f"Dashboard load timeout: {str(e)}")
            return False
    
    def validate_panels(self):
        """Validar painéis tipo gauge e stat"""
        print("\n📋 Validando painéis...")
        
        try:
            # Buscar todos os painéis
            panels = self.driver.find_elements(By.CLASS_NAME, "panel")
            print(f"   Encontrados {len(panels)} painéis")
            
            for idx, panel in enumerate(panels):
                try:
                    # Extrair informações do painel
                    title_elem = panel.find_element(By.CLASS_NAME, "panel-title")
                    title = title_elem.text if title_elem else f"Panel {idx}"
                    
                    # Verificar tipo de painel
                    panel_html = panel.get_attribute("innerHTML")
                    is_gauge = "gauge" in panel_html.lower()
                    is_stat = "stat" in panel_html.lower() or "singlestat" in panel_html.lower()
                    
                    if is_gauge or is_stat:
                        status = self.validate_single_panel(panel, title, is_gauge, is_stat)
                        if is_gauge:
                            self.results["gauges"].append(status)
                        else:
                            self.results["stats"].append(status)
                
                except Exception as e:
                    print(f"   ⚠️  Erro ao processar painel {idx}: {e}")
                    self.results["errors"].append(f"Panel {idx}: {str(e)}")
        
        except Exception as e:
            print(f"❌ Erro ao buscar painéis: {e}")
            self.results["errors"].append(f"Panel discovery: {str(e)}")
    
    def validate_single_panel(self, panel, title, is_gauge=False, is_stat=False):
        """Validar um painel individual"""
        result = {
            "title": title,
            "type": "gauge" if is_gauge else "stat",
            "status": "UNKNOWN",
            "content": "",
            "issues": []
        }
        
        try:
            # Tries múltiplos seletores para encontrar o valor
            selectors = [
                ".panel-content .singlevalue",
                ".gcell-value",
                "[data-testid='stat-value']",
                ".stat-value",
                "span.value",
                ".stat-value-inner"
            ]
            
            value_text = None
            for selector in selectors:
                try:
                    elem = panel.find_element(By.CSS_SELECTOR, selector)
                    value_text = elem.text.strip()
                    if value_text:
                        break
                except NoSuchElementException:
                    continue
            
            # Se não encontrou por CSS selector, tenta buscar todo o texto
            if not value_text:
                elements = panel.find_elements(By.CSS_SELECTOR, "span, div")
                texts = [e.text.strip() for e in elements if e.text.strip() and len(e.text.strip()) < 50]
                value_text = texts[0] if texts else "NO_VALUE"
            
            result["content"] = value_text
            
            # Validações
            issues = []
            
            # Verificar conteúdo inválido
            invalid_markers = [
                "undefined",
                "null",
                "NaN",
                "Error",
                "no data",
                "N/A",
                "",
                "–",
                "nan"
            ]
            
            if any(marker in value_text.lower() for marker in invalid_markers):
                issues.append(f"Invalid content: {value_text}")
                result["status"] = "INVALID"
            # Verificar se tem valor numérico válido
            elif any(c.isdigit() for c in value_text):
                result["status"] = "VALID"
            else:
                issues.append(f"Non-numeric content: {value_text}")
                result["status"] = "WARN"
            
            result["issues"] = issues
            
            # Log
            status_emoji = {
                "VALID": "✅",
                "INVALID": "❌",
                "WARN": "⚠️ "
            }
            emoji = status_emoji.get(result["status"], "❓")
            print(f"   {emoji} {title}: {value_text} [{result['status']}]")
            if issues:
                for issue in issues:
                    print(f"      • {issue}")
            
            return result
        
        except Exception as e:
            result["status"] = "ERROR"
            result["issues"] = [str(e)]
            print(f"   ❌ {title}: ERROR - {e}")
            return result
    
    def capture_screenshot(self, filename="grafana_gauges_validation.png"):
        """Capturar screenshot do dashboard"""
        try:
            print(f"\n📸 Capturando screenshot: {filename}")
            self.driver.save_screenshot(filename)
            print(f"   ✅ Screenshot salvo: {filename}")
            return filename
        except Exception as e:
            print(f"   ⚠️  Erro ao capturar screenshot: {e}")
            return None
    
    def generate_report(self):
        """Gerar relatório de validação"""
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE VALIDAÇÃO DOS GAUGES")
        print("="*60)
        
        # Contar status
        valid_count = sum(1 for g in self.results["gauges"] if g["status"] == "VALID")
        invalid_count = sum(1 for g in self.results["gauges"] if g["status"] == "INVALID")
        warn_count = sum(1 for g in self.results["gauges"] if g["status"] == "WARN")
        
        stats_valid = sum(1 for s in self.results["stats"] if s["status"] == "VALID")
        stats_invalid = sum(1 for s in self.results["stats"] if s["status"] == "INVALID")
        
        self.results["summary"] = {
            "total_gauges": len(self.results["gauges"]),
            "valid_gauges": valid_count,
            "invalid_gauges": invalid_count,
            "warn_gauges": warn_count,
            "total_stats": len(self.results["stats"]),
            "valid_stats": stats_valid,
            "invalid_stats": stats_invalid,
            "total_errors": len(self.results["errors"])
        }
        
        print(f"\n📈 Gauges: {valid_count} válidos, {invalid_count} inválidos, {warn_count} avisos")
        print(f"📊 Stats: {stats_valid} válidos, {stats_invalid} inválidos")
        print(f"❗ Erros gerais: {len(self.results['errors'])}")
        
        if self.results["errors"]:
            print("\n⚠️  Erros detectados:")
            for error in self.results["errors"]:
                print(f"   • {error}")
        
        # Listar gauges inválidos
        invalid_panels = [g for g in self.results["gauges"] if g["status"] == "INVALID"]
        if invalid_panels:
            print("\n❌ Painéis tipo Gauge INVÁLIDOS:")
            for panel in invalid_panels:
                print(f"   • {panel['title']}: {panel['content']}")
                for issue in panel["issues"]:
                    print(f"     → {issue}")
        
        # Listar stats inválidos
        invalid_stats = [s for s in self.results["stats"] if s["status"] == "INVALID"]
        if invalid_stats:
            print("\n❌ Painéis tipo Stat INVÁLIDOS:")
            for panel in invalid_stats:
                print(f"   • {panel['title']}: {panel['content']}")
                for issue in panel["issues"]:
                    print(f"     → {issue}")
        
        print("\n" + "="*60)
        
        return self.results
    
    def save_report(self, filename="grafana_gauges_validation_report.json"):
        """Salvar relatório em JSON"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"💾 Relatório salvo: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Erro ao salvar relatório: {e}")
            return None
    
    def run(self):
        """Executar validação completa"""
        print("\n" + "="*60)
        print("🔍 VALIDADOR DE GAUGES DO GRAFANA - EDDIE WHATSAPP")
        print("="*60)
        
        try:
            if not self.setup_driver():
                return False
            
            if not self.login():
                return False
            
            if not self.navigate_to_dashboard():
                return False
            
            self.validate_panels()
            
            # Validar conteúdo dos gauges
            invalid_gauges = [g for g in self.results["gauges"] if g["status"] == "INVALID"]
            if invalid_gauges:
                print(f"\n⚠️  {len(invalid_gauges)} gauge(s) com conteúdo inválido encontrado(s)!")
            
            # Capturar screenshot
            self.capture_screenshot()
            
            # Gerar relatório
            self.generate_report()
            self.save_report()
            
            return True
        
        except Exception as e:
            print(f"❌ Erro geral: {e}")
            self.results["errors"].append(f"General: {str(e)}")
            return False
        
        finally:
            if self.driver:
                print("\n🛑 Fechando driver...")
                self.driver.quit()

def main():
    validator = GrafanaGaugeValidator()
    success = validator.run()
    
    print("\n" + "="*60)
    if success:
        print("✅ Validação concluída com sucesso")
        # Retornar status baseado em gauges inválidos
        if validator.results["summary"].get("invalid_gauges", 0) > 0:
            print(f"⚠️  {validator.results['summary']['invalid_gauges']} gauge(s) inválido(s) detectado(s)")
            return 1
        else:
            print("✅ Todos os gauges estão válidos!")
            return 0
    else:
        print("❌ Validação falhou")
        return 2

if __name__ == "__main__":
    sys.exit(main())
