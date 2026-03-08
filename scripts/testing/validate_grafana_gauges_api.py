#!/usr/bin/env python3
"""
Validação de gauges do dashboard Grafana via API REST
Sem necessidade de Selenium - acessa diretamente a API
"""

import requests
import json
import time
import sys
from datetime import datetime

GRAFANA_URL = "http://192.168.15.2:3002/grafana"
DASHBOARD_UID = "shared-whatsapp-training"
CREDENTIALS = ("admin", "Shared@2026")

class GrafanaGaugeAPIValidator:
    """Valida gauges via API REST do Grafana"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = CREDENTIALS
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard": DASHBOARD_UID,
            "panels": [],
            "errors": [],
            "summary": {}
        }
    
    def get_dashboard(self):
        """Obter dashboard via API"""
        print("📊 Obtendo dashboard via API...")
        try:
            url = f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            dashboard = response.json()
            self.results["dashboard_data"] = dashboard
            print(f"✅ Dashboard obtido: {dashboard['dashboard']['title']}")
            return dashboard["dashboard"]
        except Exception as e:
            msg = f"Failed to get dashboard: {str(e)}"
            print(f"❌ {msg}")
            self.results["errors"].append(msg)
            return None
    
    def get_dashboard_data(self, dashboard):
        """Obter dados renderizados do dashboard"""
        print("📈 Obtendo dados renderizados...")
        try:
            # Construir payload com variáveis do dashboard
            payload = {
                "dashboard": dashboard,
                "overrides": {"fieldsOverrides": []}
            }
            
            url = f"{GRAFANA_URL}/api/dashboards/calculate-diff"
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            print("✅ Dados renderizados obtidos")
            return response.json()
        except Exception as e:
            print(f"⚠️  Erro ao obter dados renderizados: {e}")
            return None
    
    def query_prometheus(self, expr):
        """Fazer query ao Prometheus"""
        try:
            url = f"http://192.168.15.2:9090/api/v1/query"
            response = requests.get(url, params={"query": expr}, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result["status"] == "success":
                return result["data"]["result"]
            return None
        except Exception as e:
            print(f"⚠️  Erro ao consultar Prometheus: {e}")
            return None
    
    def validate_panels(self, dashboard):
        """Validar painéis tipo gauge e stat"""
        print("\n📋 Validando painéis...")
        
        panels = dashboard.get("panels", [])
        print(f"   Encontrados {len(panels)} painéis")
        
        gauge_count = 0
        stat_count = 0
        invalid_count = 0
        
        for panel in panels:
            panel_id = panel.get("id")
            title = panel.get("title", f"Panel {panel_id}")
            panel_type = panel.get("type", "unknown")
            
            if panel_type not in ["gauge", "stat", "singlestat"]:
                continue
            
            result = self.validate_panel(panel, title, panel_type)
            self.results["panels"].append(result)
            
            if panel_type == "gauge":
                gauge_count += 1
            else:
                stat_count += 1
            
            if result["status"] in ["INVALID", "ERROR"]:
                invalid_count += 1
        
        self.results["summary"] = {
            "total_gauges": gauge_count,
            "total_stats": stat_count,
            "invalid_panels": invalid_count
        }
        
        return invalid_count == 0
    
    def validate_panel(self, panel, title, panel_type):
        """Validar um painel individual"""
        result = {
            "id": panel.get("id"),
            "title": title,
            "type": panel_type,
            "status": "UNKNOWN",
            "queries": [],
            "issues": []
        }
        
        try:
            # Extrair targets (queries)
            targets = panel.get("targets", [])
            result["queries"] = [t.get("expr", "") for t in targets if t.get("expr")]
            
            if not targets:
                result["status"] = "WARN"
                result["issues"].append("No queries found")
                print(f"   ⚠️  {title} [GAUGE/STAT - No queries]")
                return result
            
            # Validar cada query
            all_valid = True
            for target in targets:
                expr = target.get("expr", "")
                if not expr:
                    continue
                
                # Query Prometheus
                prom_result = self.query_prometheus(expr)
                
                if not prom_result:
                    all_valid = False
                    result["issues"].append(f"Query returned no data: {expr}")
                else:
                    # Verificar se os valores são válidos
                    for metric in prom_result:
                        value_str = metric.get("value", [None, ""])[1]
                        
                        invalid_markers = ["nan", "NaN", "undefined", "null", ""]
                        is_invalid = any(marker in str(value_str).lower() for marker in invalid_markers)
                        
                        if is_invalid:
                            all_valid = False
                            result["issues"].append(f"Invalid value in {expr}: {value_str}")
            
            if all_valid and prom_result:
                result["status"] = "VALID"
                print(f"   ✅ {title} [{panel_type.upper()}]")
            elif not prom_result:
                result["status"] = "INVALID"
                print(f"   ❌ {title} [{panel_type.upper()} - No data]")
            else:
                result["status"] = "INVALID"
                print(f"   ❌ {title} [{panel_type.upper()} - Invalid data]")
                for issue in result["issues"]:
                    print(f"      • {issue}")
            
            return result
        
        except Exception as e:
            result["status"] = "ERROR"
            result["issues"] = [str(e)]
            print(f"   ❌ {title}: ERROR - {e}")
            return result
    
    def generate_report(self):
        """Gerar relatório"""
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE VALIDAÇÃO DOS GAUGES (VIA API)")
        print("="*60)
        
        summary = self.results["summary"]
        print(f"\n📈 Total: {summary.get('total_gauges', 0)} gauges, {summary.get('total_stats', 0)} stats")
        print(f"❗ Inválidos: {summary.get('invalid_panels', 0)}")
        
        invalid_panels = [p for p in self.results["panels"] if p["status"] == "INVALID"]
        if invalid_panels:
            print(f"\n❌ Painéis INVÁLIDOS ({len(invalid_panels)}):")
            for panel in invalid_panels:
                print(f"   • {panel['title']} [{panel['type']}]")
                for issue in panel["issues"]:
                    print(f"     → {issue}")
        
        print("\n" + "="*60)
        return len(invalid_panels) == 0
    
    def save_report(self, filename="grafana_gauges_api_validation.json"):
        """Salvar relatório em JSON"""
        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2)
            print(f"💾 Relatório salvo: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Erro ao salvar: {e}")
            return None
    
    def run(self):
        """Executar validação"""
        print("\n" + "="*60)
        print("🔍 VALIDADOR DE GAUGES VIA API REST - SHARED WHATSAPP")
        print("="*60)
        
        try:
            # Aguardar Prometheus registrar as métricas
            print("⏳ Aguardando Prometheus registrar métricas (10s)...")
            time.sleep(10)
            
            dashboard = self.get_dashboard()
            if not dashboard:
                return False
            
            success = self.validate_panels(dashboard)
            self.generate_report()
            self.save_report()
            
            return success
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            self.results["errors"].append(str(e))
            return False

def main():
    validator = GrafanaGaugeAPIValidator()
    success = validator.run()
    
    print("\n" + "="*60)
    if success:
        print("✅ TODOS OS GAUGES SÃO VÁLIDOS")
        return 0
    else:
        if validator.results["summary"].get("invalid_panels", 0) > 0:
            print(f"❌ {validator.results['summary']['invalid_panels']} painel(is) inválido(s)")
            return 1
        else:
            print("❌ Validação falhou")
            return 2

if __name__ == "__main__":
    sys.exit(main())
