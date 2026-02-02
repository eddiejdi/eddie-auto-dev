#!/usr/bin/env python3
"""
Script de integração do sistema de métricas com Grafana.

Registra:
1. Data source Prometheus
2. Dashboard Distributed Fallback
3. Alerts para eventos críticos
"""

import asyncio
import json
import requests
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GrafanaClient:
    """Cliente HTTP para Grafana API."""
    
    def __init__(self, base_url: str = "http://localhost:3000", api_key: Optional[str] = None):
        """
        Inicializa cliente Grafana.
        
        Args:
            base_url: URL base do Grafana (padrão: localhost:3000)
            api_key: API key para autenticação (opcional)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["Content-Type"] = "application/json"
    
    def health_check(self) -> bool:
        """Verifica se Grafana está acessível."""
        try:
            resp = self.session.get(f"{self.base_url}/api/health")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_datasources(self) -> list:
        """Lista data sources registradas."""
        try:
            resp = self.session.get(f"{self.base_url}/api/datasources")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get datasources: {e}")
            return []
    
    def create_prometheus_datasource(
        self,
        name: str = "Prometheus",
        url: str = "http://localhost:9090",
        is_default: bool = True
    ) -> Dict[str, Any]:
        """Registra Prometheus como data source."""
        payload = {
            "name": name,
            "type": "prometheus",
            "url": url,
            "access": "proxy",
            "isDefault": is_default,
            "jsonData": {
                "timeInterval": "15s",
                "queryTimeout": "5m"
            }
        }
        
        try:
            resp = self.session.post(f"{self.base_url}/api/datasources", json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"✅ Data source '{name}' criada/atualizada (ID: {result.get('id')})")
            return result
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.warning(f"⚠️ Data source '{name}' já existe")
                return {"exists": True}
            logger.error(f"Failed to create datasource: {e}")
            return {}
    
    def create_dashboard(self, dashboard_json: Dict[str, Any], overwrite: bool = True) -> Dict[str, Any]:
        """Cria ou atualiza dashboard."""
        payload = {
            "dashboard": dashboard_json,
            "overwrite": overwrite
        }
        
        try:
            resp = self.session.post(f"{self.base_url}/api/dashboards/db", json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"✅ Dashboard '{dashboard_json.get('title')}' criado (UID: {result.get('uid')})")
            return result
        except Exception as e:
            logger.error(f"Failed to create dashboard: {e}")
            return {}
    
    def create_alert_rule(
        self,
        title: str,
        condition: str,
        threshold: float,
        duration: str = "5m",
        severity: str = "critical"
    ) -> Dict[str, Any]:
        """Cria regra de alerta (Grafana Alerting)."""
        payload = {
            "title": title,
            "condition": condition,
            "data": [
                {
                    "refId": "A",
                    "queryType": "",
                    "model": {
                        "expr": condition,
                        "intervalFactor": 2,
                        "refId": "A"
                    },
                    "datasourceUid": "prometheus_uid",
                    "relativeTimeRange": {
                        "from": 600,
                        "to": 0
                    }
                }
            ],
            "noDataState": "NoData",
            "execErrState": "Alerting",
            "for": duration,
            "annotations": {
                "description": f"Alert triggered when {title.lower()}",
                "runbook_url": "https://example.com/runbook",
                "severity": severity
            },
            "labels": {
                "severity": severity,
                "source": "eddie-distributed-fallback"
            }
        }
        
        try:
            resp = self.session.post(f"{self.base_url}/api/v1/rules", json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"✅ Regra de alerta '{title}' criada")
            return result
        except Exception as e:
            logger.warning(f"⚠️ Alerta not fully supported: {e}")
            return {}


async def setup_grafana_integration(
    grafana_url: str = "http://localhost:3000",
    prometheus_url: str = "http://localhost:9090",
    api_key: Optional[str] = None,
    dashboard_path: Optional[str] = None
):
    """
    Configura integração completa com Grafana.
    
    Args:
        grafana_url: URL do Grafana
        prometheus_url: URL do Prometheus
        api_key: API key do Grafana (opcional)
        dashboard_path: Caminho para arquivo JSON do dashboard
    """
    client = GrafanaClient(grafana_url, api_key)
    
    print("\n📊 Iniciando integração com Grafana...")
    print(f"   Grafana: {grafana_url}")
    print(f"   Prometheus: {prometheus_url}\n")
    
    # 1. Verificar saúde
    if not client.health_check():
        print("❌ Grafana não está acessível!")
        print(f"   Verifique: {grafana_url}/api/health")
        return False
    print("✅ Grafana acessível")
    
    # 2. Criar data source Prometheus
    print("\n📡 Registrando Prometheus como data source...")
    ds_result = client.create_prometheus_datasource(
        name="Prometheus",
        url=prometheus_url,
        is_default=True
    )
    
    # 3. Carregar e criar dashboard
    print("\n📈 Carregando dashboard...")
    if dashboard_path is None:
        # Usar dashboard padrão
        dashboard_path = Path(__file__).parent / "grafana_dashboards" / "distributed-fallback-dashboard.json"
    
    dashboard_path = Path(dashboard_path)
    if not dashboard_path.exists():
        print(f"❌ Dashboard não encontrado: {dashboard_path}")
        return False
    
    with open(dashboard_path) as f:
        dashboard_json = json.load(f)
    
    # Adicionar data source ID
    if ds_result.get("id"):
        for panel in dashboard_json.get("panels", []):
            if panel.get("datasource") == "Prometheus":
                panel["datasourceUid"] = ds_result.get("uid", "prometheus")
    
    dashboard_result = client.create_dashboard(dashboard_json, overwrite=True)
    
    if not dashboard_result:
        print("⚠️ Falha ao criar dashboard")
        return False
    
    # 4. Criar alertas
    print("\n🚨 Configurando regras de alerta...")
    alerts = [
        {
            "title": "High Timeout Events",
            "condition": "increase(timeout_events_total[5m]) > 10",
            "severity": "warning"
        },
        {
            "title": "Fallback Depth Exceeded",
            "condition": "increase(fallback_depth_exceeded_total[5m]) > 0",
            "severity": "critical"
        },
        {
            "title": "High Task Failure Rate",
            "condition": "rate(task_failure_total[5m]) > 0.1",
            "severity": "warning"
        }
    ]
    
    for alert in alerts:
        client.create_alert_rule(**alert)
    
    # 5. Resumo
    print("\n" + "=" * 60)
    print("✅ INTEGRAÇÃO COM GRAFANA COMPLETA!")
    print("=" * 60)
    print(f"\n📊 Dashboard: {grafana_url}/d/{dashboard_result.get('uid')}")
    print(f"📡 Data Source: {grafana_url}/datasources")
    print(f"🚨 Alertas: {grafana_url}/alerting/alerts")
    print(f"\n📚 Documentação: {grafana_url}/api/docs")
    
    return True


def main():
    """Script principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Integra sistema de métricas com Grafana"
    )
    parser.add_argument(
        "--grafana-url",
        default="http://localhost:3000",
        help="URL do Grafana (padrão: http://localhost:3000)"
    )
    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9090",
        help="URL do Prometheus (padrão: http://localhost:9090)"
    )
    parser.add_argument(
        "--api-key",
        help="API key do Grafana (opcional)"
    )
    parser.add_argument(
        "--dashboard",
        help="Caminho para arquivo JSON do dashboard customizado"
    )
    
    args = parser.parse_args()
    
    success = asyncio.run(
        setup_grafana_integration(
            grafana_url=args.grafana_url,
            prometheus_url=args.prometheus_url,
            api_key=args.api_key,
            dashboard_path=args.dashboard
        )
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
