#!/usr/bin/env python3
"""
Validação de gauges do Shared Central via API do Grafana
Mais rápido e eficiente que Selenium
"""

import requests
import json
from datetime import datetime
import sys
import os

# Configurações
GRAFANA_BASE = os.getenv("GRAFANA_URL", "https://grafana.rpa4all.com")
DASHBOARD_UID = "shared-central"
CREDENTIALS = (os.getenv("GRAFANA_USER", "admin"), os.getenv("GRAFANA_PASS", "Shared@2026"))

class EddieCentralAPIValidator:
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = CREDENTIALS
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard": "Shared Central",
            "panels": [],
            "summary": {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "errors": 0
            }
        }
    
    def get_dashboard(self):
        """Obtém dados do dashboard via API"""
        print("📊 Obtendo dashboard via API...")
        
        try:
            url = f"{GRAFANA_BASE}/api/dashboards/uid/{DASHBOARD_UID}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            dashboard_data = response.json()
            dashboard = dashboard_data.get("dashboard", {})
            
            print(f"✅ Dashboard obtido: {dashboard.get('title', 'Unknown')}")
            print(f"   UID: {dashboard.get('uid')}")
            print(f"   Versão: {dashboard.get('version')}")
            
            return dashboard
        
        except Exception as e:
            print(f"❌ Erro ao obter dashboard: {e}")
            return None
    
    def query_prometheus(self, expr, start=None, end=None):
        """Executa query no Prometheus"""
        try:
            # Usar API do Prometheus diretamente
            prom_url = "http://192.168.15.2:9090/api/v1/query"
            
            params = {"query": expr}
            if start and end:
                params["start"] = start
                params["end"] = end
            
            response = requests.get(prom_url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {}).get("result", [])
            
            return []
        
        except Exception as e:
            print(f"   ⚠️ Erro ao consultar Prometheus: {e}")
            return None
    
    def validate_panel(self, panel):
        """Valida um painel individual"""
        panel_id = panel.get("id")
        title = panel.get("title", f"Panel {panel_id}")
        panel_type = panel.get("type", "unknown")
        
        panel_info = {
            "id": panel_id,
            "title": title,
            "type": panel_type,
            "queries": [],
            "values": [],
            "status": "UNKNOWN",
            "issues": []
        }
        
        # Filtrar apenas gauges e stats
        if panel_type not in ["gauge", "stat", "singlestat"]:
            return None
        
        try:
            # Extrair targets (queries)
            targets = panel.get("targets", [])
            
            if not targets:
                panel_info["status"] = "WARN"
                panel_info["issues"].append("Sem queries configuradas")
                return panel_info
            
            # Validar cada query
            has_valid_data = False
            has_invalid_data = False
            
            for target in targets:
                expr = target.get("expr", "")
                if not expr:
                    continue
                
                panel_info["queries"].append(expr)
                
                # Consultar Prometheus
                results = self.query_prometheus(expr)
                
                if results is None:
                    panel_info["issues"].append(f"Erro ao consultar: {expr}")
                    has_invalid_data = True
                elif not results:
                    panel_info["issues"].append(f"Sem dados: {expr}")
                    has_invalid_data = True
                else:
                    # Verificar valores retornados
                    for metric in results:
                        value_pair = metric.get("value", [None, ""])
                        if len(value_pair) >= 2:
                            value_str = str(value_pair[1])
                            panel_info["values"].append(value_str)
                            
                            # Verificar se valor é válido (não pode ser vazio/null/nan/undefined)
                            try:
                                # Tentar converter para float para validar
                                val_float = float(value_str)
                                # Se chegou aqui é um número válido
                                has_valid_data = True
                            except (ValueError, TypeError):
                                # Verificar valores especiais inválidos
                                value_lower = value_str.lower().strip()
                                invalid_markers = ["nan", "undefined", "null", ""]
                                if any(marker == value_lower for marker in invalid_markers):
                                    panel_info["issues"].append(f"Valor inválido: {value_str}")
                                    has_invalid_data = True
                                else:
                                    # Pode ser string (tags) ou outro valor válido
                                    has_valid_data = True
            
            # Determinar status
            if has_invalid_data:
                panel_info["status"] = "INVALID"
            elif has_valid_data:
                panel_info["status"] = "VALID"
            else:
                panel_info["status"] = "EMPTY"
            
            return panel_info
        
        except Exception as e:
            panel_info["status"] = "ERROR"
            panel_info["issues"].append(f"Erro: {str(e)}")
            return panel_info
    
    def validate_all_panels(self, dashboard):
        """Valida todos os painéis do dashboard"""
        print("\n📋 Validando painéis...\n")
        
        panels = dashboard.get("panels", [])
        rows = dashboard.get("rows", [])
        
        # Processar panels diretos
        all_panels = list(panels)
        
        # Processar rows (formato antigo do Grafana)
        for row in rows:
            row_panels = row.get("panels", [])
            all_panels.extend(row_panels)
        
        print(f"   Total de painéis encontrados: {len(all_panels)}")
        
        # Filtrar e validar gauges/stats
        gauge_count = 0
        
        for panel in all_panels:
            panel_result = self.validate_panel(panel)
            
            if panel_result:  # Apenas gauges/stats
                gauge_count += 1
                self.results["panels"].append(panel_result)
                
                # Print resultado
                status_emoji = {
                    "VALID": "✅",
                    "INVALID": "❌",
                    "ERROR": "🔴",
                    "WARN": "⚠️",
                    "EMPTY": "⚪"
                }
                
                emoji = status_emoji.get(panel_result["status"], "❓")
                print(f"{emoji} [{gauge_count}] {panel_result['title']}")
                print(f"    Tipo: {panel_result['type']}")
                print(f"    Queries: {len(panel_result['queries'])}")
                
                if panel_result["values"]:
                    print(f"    Valores: {', '.join(panel_result['values'][:3])}")
                
                if panel_result["issues"]:
                    print(f"    Problemas:")
                    for issue in panel_result["issues"]:
                        print(f"      • {issue}")
                
                print()
                
                # Atualizar sumário
                self.results["summary"]["total"] += 1
                if panel_result["status"] == "VALID":
                    self.results["summary"]["valid"] += 1
                elif panel_result["status"] in ["INVALID", "EMPTY"]:
                    self.results["summary"]["invalid"] += 1
                elif panel_result["status"] == "ERROR":
                    self.results["summary"]["errors"] += 1
        
        print(f"✅ Total de gauges/stats encontrados: {gauge_count}")
    
    def generate_report(self):
        """Gera relatório final"""
        print("\n" + "=" * 80)
        print("📊 RELATÓRIO DE VALIDAÇÃO - SHARED CENTRAL DASHBOARD")
        print("=" * 80)
        
        summary = self.results["summary"]
        print(f"\n📈 RESUMO:")
        print(f"   Total de gauges/stats: {summary['total']}")
        print(f"   ✅ Válidos: {summary['valid']}")
        print(f"   ❌ Inválidos: {summary['invalid']}")
        print(f"   🔴 Erros: {summary['errors']}")
        
        # Taxa de sucesso
        if summary['total'] > 0:
            success_rate = (summary['valid'] / summary['total']) * 100
            print(f"\n   📊 Taxa de sucesso: {success_rate:.1f}%")
        
        # Listar painéis com problemas
        problem_panels = [p for p in self.results["panels"] 
                         if p["status"] in ["INVALID", "ERROR", "EMPTY"]]
        
        if problem_panels:
            print(f"\n❌ PAINÉIS COM PROBLEMAS ({len(problem_panels)}):")
            for panel in problem_panels:
                print(f"\n   • {panel['title']} (ID: {panel['id']}, Tipo: {panel['type']})")
                print(f"     Status: {panel['status']}")
                
                if panel['queries']:
                    print(f"     Queries:")
                    for query in panel['queries']:
                        print(f"       - {query}")
                
                if panel['values']:
                    print(f"     Valores: {', '.join(panel['values'][:5])}")
                
                if panel['issues']:
                    print(f"     Problemas:")
                    for issue in panel['issues']:
                        print(f"       - {issue}")
        
        print("\n" + "=" * 80)
        
        # Salvar resultado em JSON
        output_file = "/tmp/shared_central_validation_api.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Relatório detalhado salvo em: {output_file}")
        
        return summary['invalid'] == 0 and summary['errors'] == 0
    
    def run(self):
        """Executa validação completa"""
        print("=" * 80)
        print("🚀 VALIDAÇÃO DE GAUGES - SHARED CENTRAL (VIA API)")
        print("=" * 80)
        print(f"🕐 Timestamp: {self.results['timestamp']}")
        print(f"🔗 Dashboard UID: {DASHBOARD_UID}")
        
        try:
            # Obter dashboard
            dashboard = self.get_dashboard()
            if not dashboard:
                return False
            
            # Validar painéis
            self.validate_all_panels(dashboard)
            
            # Gerar relatório
            success = self.generate_report()
            
            return success
        
        except Exception as e:
            print(f"\n❌ Erro crítico: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    validator = EddieCentralAPIValidator()
    success = validator.run()
    
    sys.exit(0 if success else 1)
