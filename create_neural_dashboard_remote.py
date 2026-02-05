#!/usr/bin/env python3
"""
Cria um Dashboard Neural no Grafana via servidor remoto.
"""

import json
import sys
import subprocess

# Configuração
GRAFANA_URL = "http://localhost:3002"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "admin"

# Dashboard JSON estruturado como rede neural
DASHBOARD_CONFIG = {
    "dashboard": {
        "title": "🧠 Neural Network - Server Components",
        "description": "Representação neural dos componentes do servidor homelab",
        "tags": ["neural", "infrastructure", "monitoring"],
        "timezone": "browser",
        "refresh": "30s",
        "schemaVersion": 38,
        "version": 0,
        "uid": "neural-network",
        "panels": [
            {
                "id": 1,
                "title": "🌐 Sistema Central - Status Geral",
                "type": "stat",
                "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "count(up{job=~'.*'})",
                        "legendFormat": "Serviços Ativos"
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
                    }
                }
            },
            {
                "id": 2,
                "title": "🐳 Docker Containers - Memory Usage",
                "type": "piechart",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "container_memory_usage_bytes / 1024 / 1024",
                        "legendFormat": "{{name}}"
                    }
                ],
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single"},
                    "displayLabels": ["value"]
                },
                "fieldConfig": {
                    "defaults": {
                        "unit": "MB",
                        "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}}
                    }
                }
            },
            {
                "id": 3,
                "title": "🤖 Agentes - Status de Conexão",
                "type": "table",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "up{job=~'eddie.*|specialized.*|coordinator.*|github.*'}",
                        "format": "table",
                        "instant": True
                    }
                ],
                "options": {
                    "showHeader": True,
                    "sortBy": [{"displayName": "Value", "desc": True}]
                }
            },
            {
                "id": 4,
                "title": "💾 CPU - Utilização Neural",
                "type": "graph",
                "gridPos": {"h": 8, "w": 8, "x": 0, "y": 16},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)",
                        "legendFormat": "CPU %"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 20
                        },
                        "unit": "percent",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 60},
                                {"color": "red", "value": 80}
                            ]
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 5,
                "title": "🧠 Memory - Utilização Neural",
                "type": "graph",
                "gridPos": {"h": 8, "w": 8, "x": 8, "y": 16},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
                        "legendFormat": "Memory %"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 20
                        },
                        "unit": "percent",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 70},
                                {"color": "red", "value": 85}
                            ]
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 6,
                "title": "💿 Disk - Utilização Neural",
                "type": "graph",
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 16},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "(1 - (node_filesystem_avail_bytes{fstype=~'ext4|xfs'} / node_filesystem_size_bytes{fstype=~'ext4|xfs'})) * 100",
                        "legendFormat": "Disk % - {{device}}"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 20
                        },
                        "unit": "percent",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 75},
                                {"color": "red", "value": 90}
                            ]
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 7,
                "title": "🌐 Network - Tráfego Neural",
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "rate(node_network_receive_bytes_total[5m])",
                        "legendFormat": "RX - {{device}}"
                    },
                    {
                        "refId": "B",
                        "expr": "rate(node_network_transmit_bytes_total[5m])",
                        "legendFormat": "TX - {{device}}"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 10
                        },
                        "unit": "Bps"
                    }
                },
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}
                }
            },
            {
                "id": 8,
                "title": "📦 Docker Network - Tráfego de Containers",
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "rate(container_network_receive_bytes_total[5m])",
                        "legendFormat": "RX - {{name}}"
                    },
                    {
                        "refId": "B",
                        "expr": "rate(container_network_transmit_bytes_total[5m])",
                        "legendFormat": "TX - {{name}}"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 10
                        },
                        "unit": "Bps"
                    }
                },
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}
                }
            }
        ],
        "templating": {
            "list": []
        }
    },
    "overwrite": True
}

def create_dashboard():
    """Cria o dashboard via curl"""
    
    dashboard_json = json.dumps(DASHBOARD_CONFIG)
    
    # Comando curl para criar/atualizar dashboard
    cmd = [
        "curl",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-u", f"{GRAFANA_USER}:{GRAFANA_PASSWORD}",
        f"{GRAFANA_URL}/api/dashboards/db",
        "-d", dashboard_json
    ]
    
    print("🧠 Criando Dashboard Neural no Grafana...")
    print(f"📍 URL: {GRAFANA_URL}\n")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            if response.get('status') == 'success' or response.get('id'):
                print("✅ Dashboard criado com sucesso!")
                print(f"📊 Dashboard URL: {GRAFANA_URL}/d/{response.get('uid', 'neural-network')}")
                print(f"📋 Dashboard ID: {response.get('id', 'N/A')}")
                return True
            else:
                print(f"⚠️  Resposta: {response}")
                return False
        else:
            print(f"❌ Erro: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout na conexão com Grafana")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao processar resposta JSON: {e}")
        print(f"Resposta: {result.stdout[:200]}")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    success = create_dashboard()
    sys.exit(0 if success else 1)
