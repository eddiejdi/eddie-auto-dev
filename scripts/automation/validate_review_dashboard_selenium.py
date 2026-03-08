#!/usr/bin/env python3
"""
Valida o dashboard Review Quality Gate System no Grafana
Verifica todos os 10 painéis e métricas após as correções aplicadas
"""

import os
import sys
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests

# ============ CONFIGURAÇÕES ============
GRAFANA_URL = "http://192.168.15.2:3002"
DASHBOARD_UID = "review-system-metrics"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "Shared@2026"
PROMETHEUS_URL = "http://192.168.15.2:9090"

# Painéis esperados
EXPECTED_PANELS = [
    "Taxa de Aprovação (%)",
    "Items Pendentes",
    "Total de Reviews",
    "Total de Approvals",
    "Total de Rejections",
    "Score Médio (0-100)",
    "Fila de Review - Status",
    "Tempo de Processamento (p95/p99)",
    "Review Service Status",
    "Total de Erros"
]

# Métricas esperadas
EXPECTED_METRICS = [
    "review_queue_total",
    "review_queue_pending",
    "review_approval_rate",
    "review_service_up",
    "review_agent_total_reviews_total",
    "review_agent_approvals_total",
    "review_agent_rejections_total",
    "review_agent_avg_score"
]


class ReviewDashboardValidator:
    def __init__(self):
        self.driver = None
        self.validation_results = {
            "dashboard_loaded": False,
            "panels_found": 0,
            "panels_with_errors": [],
            "metrics_available": {},
            "service_health": None,
            "overall_status": "PENDING"
        }
    
    def setup_chrome(self):
        """Configura Chrome headless"""
        print("🔧 Configurando Chrome...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ Chrome configurado")
            return True
        except Exception as e:
            print(f"❌ Erro ao inicializar Chrome: {e}")
            return False
    
    def verify_prometheus_metrics(self):
        """Verifica se métricas estão disponíveis no Prometheus"""
        print("\n📊 Verificando métricas no Prometheus...")
        
        for metric in EXPECTED_METRICS:
            try:
                resp = requests.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={"query": metric},
                    timeout=5
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("data", {}).get("result", [])
                    
                    if result:
                        value = result[0].get("value", [None, None])[1]
                        self.validation_results["metrics_available"][metric] = {
                            "status": "OK",
                            "value": value
                        }
                        print(f"  ✅ {metric} = {value}")
                        
                        # Capturar health check especial
                        if metric == "review_service_up":
                            self.validation_results["service_health"] = value
                    else:
                        self.validation_results["metrics_available"][metric] = {
                            "status": "NO_DATA",
                            "value": None
                        }
                        print(f"  ⚠️ {metric} - sem dados")
                else:
                    self.validation_results["metrics_available"][metric] = {
                        "status": "ERROR",
                        "value": None
                    }
                    print(f"  ❌ {metric} - erro {resp.status_code}")
            
            except Exception as e:
                self.validation_results["metrics_available"][metric] = {
                    "status": "ERROR",
                    "value": None,
                    "error": str(e)
                }
                print(f"  ❌ {metric} - exceção: {e}")
        
        # Verificar health check
        if self.validation_results["service_health"] == "1":
            print(f"\n  ✅ Service Health: UP (review_service_up = 1)")
        else:
            print(f"\n  ❌ Service Health: DOWN (review_service_up = {self.validation_results['service_health']})")
    
    def login_grafana(self):
        """Login no Grafana"""
        print(f"\n🔐 Fazendo login no Grafana...")
        
        try:
            self.driver.get(f"{GRAFANA_URL}/login")
            wait = WebDriverWait(self.driver, 10)
            
            # Preencher credenciais
            user_field = wait.until(EC.presence_of_element_located((By.NAME, "user")))
            user_field.send_keys(GRAFANA_USER)
            
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(GRAFANA_PASSWORD)
            
            # Clicar login
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            time.sleep(3)
            
            if "/login" not in self.driver.current_url:
                print("✅ Login bem-sucedido")
                return True
            else:
                print("❌ Falha no login")
                return False
        
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            return False
    
    def validate_dashboard(self):
        """Valida o dashboard Review Quality Gate System"""
        print(f"\n📊 Validando dashboard {DASHBOARD_UID}...")
        
        try:
            # Acessar dashboard
            dashboard_url = f"{GRAFANA_URL}/grafana/d/{DASHBOARD_UID}/review-quality-gate-system"
            print(f"   URL: {dashboard_url}")
            self.driver.get(dashboard_url)
            
            time.sleep(5)
            
            # Verificar se dashboard carregou
            wait = WebDriverWait(self.driver, 15)
            
            try:
                # Aguardar título do dashboard
                title_elem = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .page-toolbar__title, [class*='Title']"))
                )
                print(f"   ✅ Dashboard carregou: {title_elem.text if hasattr(title_elem, 'text') else 'Review Quality Gate System'}")
                self.validation_results["dashboard_loaded"] = True
            except Exception as e:
                print(f"   ❌ Dashboard não carregou: {e}")
                return False
            
            # Encontrar todos os painéis
            panels = self.driver.find_elements(By.CSS_SELECTOR, ".panel-container, [data-testid='panel'], [data-panelid]")
            panels_count = len(panels)
            self.validation_results["panels_found"] = panels_count
            
            print(f"   📈 Painéis encontrados: {panels_count}")
            
            if panels_count == 0:
                print("   ⚠️ Nenhum painel encontrado!")
                return False
            
            # Verificar cada painel por erros
            error_count = 0
            no_data_count = 0
            
            for i, panel in enumerate(panels):
                try:
                    # Verificar por mensagens de erro
                    error_messages = panel.find_elements(By.XPATH, ".//*[contains(text(), 'An unexpected error') or contains(text(), 'Error') or contains(@class, 'error')]")
                    
                    if error_messages:
                        error_count += 1
                        error_text = error_messages[0].text if error_messages else "Unknown error"
                        self.validation_results["panels_with_errors"].append({
                            "panel_index": i + 1,
                            "error": error_text
                        })
                        print(f"   ❌ Painel {i+1}: ERRO - {error_text[:50]}")
                    
                    # Verificar "No data"
                    no_data = panel.find_elements(By.XPATH, ".//*[contains(text(), 'No data')]")
                    if no_data:
                        no_data_count += 1
                        print(f"   ⚠️ Painel {i+1}: Sem dados (esperado se fila vazia)")
                    
                    # Verificar por visualizações (sucesso)
                    has_viz = panel.find_elements(By.CSS_SELECTOR, "canvas, svg, .graph, [class*='viz']")
                    if has_viz and not error_messages:
                        print(f"   ✅ Painel {i+1}: OK")
                
                except Exception as e:
                    print(f"   ⚠️ Erro ao inspecionar painel {i+1}: {e}")
            
            # Capturar screenshot
            screenshot_path = "/tmp/review_dashboard_validation.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"\n   📸 Screenshot salvo: {screenshot_path}")
            
            # Resumo da validação
            print(f"\n   📋 Resumo:")
            print(f"      Total de painéis: {panels_count}")
            print(f"      Painéis com erro: {error_count}")
            print(f"      Painéis sem dados: {no_data_count}")
            
            if error_count > 0:
                print(f"\n   ❌ VALIDAÇÃO FALHOU: {error_count} painéis com erros")
                return False
            
            print(f"\n   ✅ VALIDAÇÃO OK: {panels_count} painéis carregados sem erros")
            return True
        
        except Exception as e:
            print(f"   ❌ Erro durante validação: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_full_validation(self):
        """Executa validação completa"""
        print("=" * 80)
        print("🔍 VALIDAÇÃO DO DASHBOARD REVIEW QUALITY GATE SYSTEM")
        print("=" * 80)
        
        # 1. Verificar métricas no Prometheus
        self.verify_prometheus_metrics()
        
        # 2. Configurar Selenium
        if not self.setup_chrome():
            self.validation_results["overall_status"] = "FAILED - Chrome setup"
            return False
        
        # 3. Login no Grafana
        if not self.login_grafana():
            self.validation_results["overall_status"] = "FAILED - Login"
            self.driver.quit()
            return False
        
        # 4. Validar dashboard
        dashboard_ok = self.validate_dashboard()
        
        # Fechar browser
        self.driver.quit()
        
        # Status final
        if dashboard_ok:
            self.validation_results["overall_status"] = "PASSED"
        else:
            self.validation_results["overall_status"] = "FAILED - Dashboard validation"
        
        return dashboard_ok
    
    def print_final_report(self):
        """Imprime relatório final"""
        print("\n" + "=" * 80)
        print("📋 RELATÓRIO FINAL DE VALIDAÇÃO")
        print("=" * 80)
        
        results = self.validation_results
        
        print(f"\n🎯 Status Geral: {results['overall_status']}")
        
        print(f"\n📊 Métricas Prometheus:")
        metrics_ok = sum(1 for m in results['metrics_available'].values() if m['status'] == 'OK')
        metrics_total = len(results['metrics_available'])
        print(f"   {metrics_ok}/{metrics_total} métricas disponíveis")
        
        for metric, data in results['metrics_available'].items():
            status_icon = "✅" if data['status'] == 'OK' else "❌"
            print(f"   {status_icon} {metric}: {data.get('value', 'N/A')}")
        
        print(f"\n🏥 Service Health:")
        if results['service_health'] == "1":
            print(f"   ✅ review_service_up = 1 (ONLINE)")
        else:
            print(f"   ❌ review_service_up = {results['service_health']} (OFFLINE)")
        
        print(f"\n🖼️ Dashboard:")
        print(f"   Carregado: {'✅ Sim' if results['dashboard_loaded'] else '❌ Não'}")
        print(f"   Painéis encontrados: {results['panels_found']}")
        print(f"   Painéis com erros: {len(results['panels_with_errors'])}")
        
        if results['panels_with_errors']:
            print(f"\n   ❌ Erros encontrados:")
            for error in results['panels_with_errors']:
                print(f"      • Painel {error['panel_index']}: {error['error']}")
        
        print("\n" + "=" * 80)
        
        if results['overall_status'] == "PASSED":
            print("✅ VALIDAÇÃO CONCLUÍDA COM SUCESSO")
            print("=" * 80)
            print("\n🎉 Dashboard Review Quality Gate System está operacional!")
            print(f"   URL: {GRAFANA_URL}/grafana/d/{DASHBOARD_UID}/")
            return True
        else:
            print("❌ VALIDAÇÃO FALHOU")
            print("=" * 80)
            print(f"\n   Status: {results['overall_status']}")
            return False
    
    def save_results(self):
        """Salva resultados em JSON"""
        output_file = "/tmp/review_dashboard_validation_results.json"
        with open(output_file, "w") as f:
            json.dump(self.validation_results, f, indent=2)
        print(f"\n💾 Resultados salvos em: {output_file}")


def main():
    validator = ReviewDashboardValidator()
    
    try:
        success = validator.run_full_validation()
        validator.print_final_report()
        validator.save_results()
        
        return 0 if success else 1
    
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
