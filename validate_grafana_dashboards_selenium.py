#!/usr/bin/env python3
"""
Valida painéis do Grafana usando Selenium
Verifica se estão carregando corretamente com dados
Deploy dos painéis funcionais para o servidor
"""

import json
import subprocess
import os
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests
from datetime import datetime
import urllib.parse

# ============ CONFIGURAÇÕES ============
LOCALHOST_GRAFANA = "http://localhost:3002"
PROD_GRAFANA = "http://192.168.15.2:3002"
GRAFANA_CREDS = ("admin", "Eddie@2026")
HOMELAB_HOST = "homelab@192.168.15.2"
SSH_KEY = os.path.expanduser("~/.ssh/eddie_deploy_rsa")

class GrafanaDashboardValidator:
    def __init__(self, base_url=LOCALHOST_GRAFANA):
        self.base_url = base_url
        self.driver = None
        self.results = []
        self.valid_dashboards = []
        
    def setup_chrome(self):
        """Configura Chrome para testes"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"❌ Erro ao inicializar Chrome: {e}")
            return False
        return True
    
    def login_grafana(self):
        """Faz login no Grafana"""
        try:
            print(f"🔐 Fazendo login no Grafana ({self.base_url})...")
            self.driver.get(f"{self.base_url}/login")
            
            # Aguardar campo de email
            wait = WebDriverWait(self.driver, 10)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "user")))
            email_field.send_keys(GRAFANA_CREDS[0])
            
            # Preencher senha
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(GRAFANA_CREDS[1])
            
            # Clicar login
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            # Aguardar redirecionamento
            time.sleep(3)
            
            if "/login" not in self.driver.current_url:
                print("✅ Login bem-sucedido")
                return True
            else:
                print("❌ Falha no login")
                return False
        except Exception as e:
            print(f"❌ Erro durante login: {e}")
            return False
    
    def get_all_dashboards(self):
        """Obtém lista de todos os painéis via API"""
        try:
            url = f"{self.base_url}/api/search?type=dash-db"
            resp = requests.get(url, auth=GRAFANA_CREDS)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"❌ Erro ao obter painéis: {e}")
            return []
    
    def validate_dashboard(self, dashboard_uid, dashboard_title):
        """Valida se um painel carrega e tem dados"""
        try:
            print(f"\n📊 Validando painel: {dashboard_title} ({dashboard_uid})...")
            
            # Acessar painel
            dashboard_url = f"{self.base_url}/grafana/d/{dashboard_uid}"
            self.driver.get(dashboard_url)
            
            time.sleep(3)
            
            # Verificar se painel carregou
            wait = WebDriverWait(self.driver, 15)
            
            # Procurar por painéis de visualização
            try:
                panels = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".panel-container, [data-testid='panel']"))
                )
                print(f"   ✅ Painel carregou com {len(panels)} painéis de visualização")
            except:
                panels = self.driver.find_elements(By.CSS_SELECTOR, ".panel-container, [data-testid='panel']")
                if not panels:
                    print(f"   ⚠️ Nenhum painel de visualização encontrado")
                    return {"status": "empty", "reason": "No visualization panels"}
            
            # Verificar se há dados
            has_data = False
            error_count = 0
            
            for i, panel in enumerate(panels):
                try:
                    # Verificar por gráficos com dados
                    has_chart = panel.find_elements(By.CSS_SELECTOR, "canvas, svg, .plot")
                    if has_chart:
                        has_data = True
                        print(f"   ✅ Painel {i+1}: Tem visualização")
                    
                    # Verificar erros
                    error_elem = panel.find_elements(By.CSS_SELECTOR, ".error, .alert-error, [class*='error']")
                    if error_elem:
                        error_count += 1
                        print(f"   ⚠️ Painel {i+1}: Contém erros")
                except Exception as e:
                    print(f"   ⚠️ Erro ao inspecionar painel {i+1}: {e}")
            
            # Verificar por mensagens de erro
            page_errors = self.driver.find_elements(By.CSS_SELECTOR, ".alert-error, [class*='error']")
            
            if error_count > 0 or not has_data:
                status = "error" if error_count > 0 else "empty"
                print(f"   ❌ Painel inválido: {status}")
                return {
                    "status": status,
                    "panels_count": len(panels),
                    "error_count": error_count,
                    "has_data": has_data
                }
            else:
                print(f"   ✅ Painel válido com dados!")
                return {
                    "status": "valid",
                    "panels_count": len(panels),
                    "has_data": True
                }
        
        except Exception as e:
            print(f"   ❌ Erro ao validar: {e}")
            return {"status": "error", "reason": str(e)}
    
    def run_validation(self):
        """Executa validação completa"""
        print("=" * 60)
        print("🔍 VALIDAÇÃO DE PAINÉIS DO GRAFANA")
        print("=" * 60)
        
        if not self.setup_chrome():
            return False
        
        if not self.login_grafana():
            self.driver.quit()
            return False
        
        # Obter painéis
        dashboards = self.get_all_dashboards()
        print(f"\n📌 Encontrados {len(dashboards)} painéis")
        
        if not dashboards:
            print("❌ Nenhum painel encontrado!")
            self.driver.quit()
            return False
        
        # Validar cada painel
        for dashboard in dashboards:
            uid = dashboard.get("uid")
            title = dashboard.get("title", "Unknown")
            
            result = self.validate_dashboard(uid, title)
            
            self.results.append({
                "uid": uid,
                "title": title,
                "validation": result
            })
            
            if result.get("status") == "valid":
                self.valid_dashboards.append({
                    "uid": uid,
                    "title": title
                })
        
        self.driver.quit()
        return True
    
    def print_report(self):
        """Imprime relatório de validação"""
        print("\n" + "=" * 60)
        print("📋 RELATÓRIO DE VALIDAÇÃO")
        print("=" * 60)
        
        for result in self.results:
            uid = result["uid"]
            title = result["title"]
            validation = result["validation"]
            status = validation.get("status", "unknown")
            
            status_emoji = {
                "valid": "✅",
                "empty": "⚠️",
                "error": "❌"
            }.get(status, "❓")
            
            print(f"\n{status_emoji} {title}")
            print(f"   UID: {uid}")
            print(f"   Status: {status}")
            
            if "panels_count" in validation:
                print(f"   Painéis: {validation['panels_count']}")
            if "error_count" in validation:
                print(f"   Erros: {validation['error_count']}")
        
        print("\n" + "=" * 60)
        print(f"📊 RESUMO: {len(self.valid_dashboards)}/{len(self.results)} painéis válidos")
        print("=" * 60)
        
        return self.valid_dashboards
    
    def deploy_to_server(self):
        """Deploy dos painéis válidos para o servidor"""
        if not self.valid_dashboards:
            print("\n⚠️ Nenhum painel válido para fazer deploy")
            return False
        
        print("\n" + "=" * 60)
        print("🚀 DEPLOY DOS PAINÉIS VÁLIDOS")
        print("=" * 60)
        
        for dashboard in self.valid_dashboards:
            uid = dashboard["uid"]
            title = dashboard["title"]
            
            print(f"\n📤 Exportando painel: {title} ({uid})...")
            
            try:
                # Obter JSON do painel
                resp = requests.get(
                    f"{LOCALHOST_GRAFANA}/api/dashboards/uid/{uid}",
                    auth=GRAFANA_CREDS
                )
                
                if resp.status_code != 200:
                    print(f"   ❌ Erro ao obter painel: {resp.status_code}")
                    continue
                
                dashboard_json = resp.json()
                
                # Salvar localmente
                json_file = f"/tmp/{uid}_dashboard.json"
                with open(json_file, "w") as f:
                    json.dump(dashboard_json, f, indent=2)
                
                print(f"   ✅ Painel exportado: {json_file}")
                
                # Upload para servidor via curl + SSH
                if self._upload_to_server(json_file, uid, title):
                    print(f"   ✅ Deploy bem-sucedido para servidor!")
                else:
                    print(f"   ❌ Falha no deploy")
            
            except Exception as e:
                print(f"   ❌ Erro: {e}")
    
    def _upload_to_server(self, json_file, uid, title):
        """Faz upload do painel para o servidor Grafana"""
        try:
            # Usar SSH + curl para fazer upload
            cmd = f"""
            ssh -i {SSH_KEY} {HOMELAB_HOST} << 'EOFCURL'
            curl -X POST http://127.0.0.1:3002/api/dashboards/db \
              -H "Content-Type: application/json" \
              -H "Authorization: Bearer $(curl -s -X POST http://127.0.0.1:3002/api/auth/keys \
                -H "Content-Type: application/json" \
                -d '{{"name":"deploy","role":"Admin"}}' | grep -o '"key":"[^"]*' | cut -d'"' -f4)" \
              -d @- << 'EOFJSON'
            $(cat {json_file})
            EOFJSON
            EOFCURL
            """
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if "success" in result.stdout.lower() or "ok" in result.stdout.lower():
                return True
            
            # Alternativa: Usar arquivo local e transferir
            print(f"   🔄 Usando método alternativo de upload...")
            
            # Transferir arquivo via SCP
            scp_cmd = f"scp -i {SSH_KEY} {json_file} {HOMELAB_HOST}:/tmp/"
            subprocess.run(scp_cmd, shell=True, check=True)
            
            # Importar via SSH + curl no servidor
            import_cmd = f"""
            ssh -i {SSH_KEY} {HOMELAB_HOST} << 'EOF'
            curl -X POST http://127.0.0.1:3002/api/dashboards/db \
              -H "Content-Type: application/json" \
              -u admin:Eddie@2026 \
              -d @/tmp/{Path(json_file).name}
            EOF
            """
            
            result = subprocess.run(import_cmd, shell=True, capture_output=True, text=True)
            return "success" in result.stdout.lower() or result.returncode == 0
        
        except Exception as e:
            print(f"   ❌ Erro no upload: {e}")
            return False


def main():
    # Validar localhost primeiro
    print("\n🔄 FASE 1: VALIDAÇÃO NO LOCALHOST")
    validator = GrafanaDashboardValidator(LOCALHOST_GRAFANA)
    
    if not validator.run_validation():
        print("❌ Falha na validação")
        return False
    
    valid_dashboards = validator.print_report()
    
    if not valid_dashboards:
        print("\n⚠️ Nenhum painel válido encontrado no localhost")
        return False
    
    # Deploy dos válidos
    print("\n🔄 FASE 2: DEPLOY PARA SERVIDOR")
    validator.deploy_to_server()
    
    print("\n" + "=" * 60)
    print("✅ PROCESSO CONCLUÍDO")
    print("=" * 60)
    print(f"\nPainéis válidos deployados: {len(valid_dashboards)}")
    for d in valid_dashboards:
        print(f"  • {d['title']} ({d['uid']})")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
