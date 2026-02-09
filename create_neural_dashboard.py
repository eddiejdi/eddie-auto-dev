#!/usr/bin/env python3
"""
Cria um Dashboard Neural no Grafana representando os componentes do servidor.
Este dashboard mostra uma representação visual tipo rede neural dos componentes.
"""

import json
import os
import requests
import sys
from typing import Dict, List, Any

# Configuração
HOMELAB_HOST = os.environ.get("HOMELAB_HOST", "localhost")
GRAFANA_URL = os.environ.get("GRAFANA_URL", f"http://{HOMELAB_HOST}:3000")
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "Eddie@2026")
PROMETHEUS_DATASOURCE = "Prometheus"

# Mapeamento de componentes do servidor
COMPONENTS = {
    "Docker Containers": {
        "color": "#FF9830",
        "items": [
            {"name": "Open WebUI", "metric": "container_memory_usage_bytes{name='open-webui'}"},
            {"name": "PostgreSQL", "metric": "container_memory_usage_bytes{name='eddie-postgres'}"},
            {"name": "Grafana", "metric": "container_memory_usage_bytes{name='grafana'}"},
            {"name": "Prometheus", "metric": "container_memory_usage_bytes{name='prometheus'}"},
            {"name": "NextCloud", "metric": "container_memory_usage_bytes{name='nextcloud-app'}"},
            {"name": "WAHA", "metric": "container_memory_usage_bytes{name='waha'}"},
            {"name": "Code Runner", "metric": "container_memory_usage_bytes{name='code-runner'}"},
        ]
    },
    "Agentes": {
        "color": "#37872D",
        "items": [
            {"name": "Specialized Agents API", "metric": "up{job='specialized-agents-api'}"},
            {"name": "Coordinator", "metric": "up{job='eddie-coordinator'}"},
            {"name": "Conversation Monitor", "metric": "up{job='eddie-conversation-monitor'}"},
            {"name": "GitHub Actions", "metric": "up{job='github-actions'}"},
        ]
    },
    "Infraestrutura": {
        "color": "#0099CC",
        "items": [
            {"name": "CPU", "metric": "node_cpu_seconds_total"},
            {"name": "Memory", "metric": "node_memory_MemFree_bytes"},
            {"name": "Disk", "metric": "node_filesystem_free_bytes"},
            {"name": "Network", "metric": "node_network_receive_bytes_total"},
        ]
    },
    "Aplicações": {
        "color": "#C41A16",
        "items": [
            {"name": "Telegram Bot", "metric": "up{job='eddie-telegram-bot'}"},
            {"name": "WhatsApp Bot", "metric": "up{job='eddie-whatsapp-bot'}"},
            {"name": "Email Cleaner", "metric": "up{job='email-cleaner'}"},
        ]
    }
}

class GrafanaDashboardCreator:
    def __init__(self, url: str, user: str, password: str):
        self.url = url
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.session.auth = (user, password)
        
    def get_datasource_id(self, name: str) -> int:
        """Obtém ID do datasource pelo nome"""
        resp = self.session.get(f"{self.url}/api/datasources")
        if resp.status_code != 200:
            print(f"❌ Erro ao listar datasources: {resp.status_code}")
            return None
        
        data = resp.json()
        for ds in data:
            if ds['name'] == name:
                return ds['id']
        
        print(f"❌ Datasource '{name}' não encontrado")
        return None
    
    def create_dashboard(self) -> bool:
        """Cria o dashboard neural"""
        datasource_id = self.get_datasource_id(PROMETHEUS_DATASOURCE)
        if not datasource_id:
            return False
        
        dashboard = {
            "dashboard": {
                "title": "🧠 Neural Network - Server Components",
                "description": "Representação neural dos componentes do servidor",
                "tags": ["neural", "infrastructure", "components"],
                "timezone": "browser",
                "refresh": "30s",
                "schemaVersion": 38,
                "version": 1,
                "panels": self._create_panels(datasource_id),
                "templating": {
                    "list": []
                }
            },
            "overwrite": True
        }
        
        resp = self.session.post(
            f"{self.url}/api/dashboards/db",
            json=dashboard,
            headers={"Content-Type": "application/json"}
        )
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            print(f"✅ Dashboard criado: {data.get('url', 'dashboard')}")
            return True
        else:
            print(f"❌ Erro ao criar dashboard: {resp.status_code} - {resp.text}")
            return False
    
    def _create_panels(self, datasource_id: int) -> List[Dict[str, Any]]:
        """Cria os painéis do dashboard"""
        panels = []
        panel_id = 1
        
        # Painel central: Visão geral do sistema
        panels.append(self._create_system_overview_panel(panel_id, datasource_id))
        panel_id += 1
        
        # Painéis por categoria
        y_position = 8
        x_positions = [0, 12]
        position_index = 0
        
        for category, data in COMPONENTS.items():
            for i, item in enumerate(data['items']):
                x = x_positions[position_index % 2]
                
                panel = self._create_metric_panel(
                    panel_id=panel_id,
                    title=item['name'],
                    category=category,
                    metric=item['metric'],
                    datasource_id=datasource_id,
                    x=x,
                    y=y_position,
                    color=data['color']
                )
                panels.append(panel)
                panel_id += 1
                
                if (i + 1) % 2 == 0:
                    y_position += 8
                position_index += 1
        
        return panels
    
    def _create_system_overview_panel(self, panel_id: int, datasource_id: int) -> Dict[str, Any]:
        """Cria painel central de visão geral"""
        return {
            "id": panel_id,
            "title": "🌐 Neural Network Overview",
            "type": "stat",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
            "targets": [
                {
                    "refId": "A",
                    "expr": "count(up{job=~'.*'})",
                    "legendFormat": "Active Services",
                    "datasource": {"type": "prometheus", "uid": str(datasource_id)}
                }
            ],
            "options": {
                "graphMode": "none",
                "orientation": "auto",
                "textMode": "auto",
                "colorMode": "background",
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"]
                }
            },
            "fieldConfig": {
                "defaults": {
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "red", "value": None},
                            {"color": "yellow", "value": 10},
                            {"color": "green", "value": 15}
                        ]
                    },
                    "unit": "short",
                    "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}}
                },
                "overrides": []
            }
        }
    
    def _create_metric_panel(self, panel_id: int, title: str, category: str, 
                            metric: str, datasource_id: int, x: int, y: int, color: str) -> Dict[str, Any]:
        """Cria painel para uma métrica específica"""
        return {
            "id": panel_id,
            "title": f"📡 {title}",
            "type": "graph",
            "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
            "targets": [
                {
                    "refId": "A",
                    "expr": metric,
                    "legendFormat": title,
                    "datasource": {"type": "prometheus", "uid": str(datasource_id)}
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "custom": {
                        "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                        "lineWidth": 2,
                        "fillOpacity": 10
                    },
                    "color": {"mode": "fixed", "fixedColor": color},
                    "thresholds": {"mode": "off"}
                }
            },
            "options": {
                "legend": {"showLegend": True, "placement": "bottom"},
                "tooltip": {"mode": "single"}
            }
        }

def main():
    print("🧠 Criando Dashboard Neural no Grafana...\n")
    print("📊 Componentes a mapear:")
    for category, data in COMPONENTS.items():
        print(f"  {category}: {len(data['items'])} componentes")
    
    creator = GrafanaDashboardCreator(GRAFANA_URL, GRAFANA_USER, GRAFANA_PASSWORD)
    
    print("\n🔍 Verificando Grafana...")
    if creator.get_datasource_id(PROMETHEUS_DATASOURCE) is None:
        print("❌ Prometheus não está configurado como datasource no Grafana")
        sys.exit(1)
    
    print("✅ Grafana e Prometheus prontos\n")
    print("⚙️  Criando dashboard...")
    
    if creator.create_dashboard():
        print("\n✅ Dashboard neural criado com sucesso!")
        print(f"📍 Acesse em: {GRAFANA_URL}/d/neural-network")
    else:
        print("\n❌ Erro ao criar dashboard")
        sys.exit(1)

if __name__ == "__main__":
    main()
