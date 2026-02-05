#!/bin/bash
# Script para criar dashboard neural no Grafana sem autenticação
# Usando docker exec para contornar autenticação

GRAFANA_CONTAINER="grafana"
DASHBOARD_FILE="/tmp/neural_dashboard.json"
GRAFANA_DASHBOARDS_DIR="/var/lib/grafana/dashboards"

# Dashboard JSON completo
cat > "$DASHBOARD_FILE" << 'EOFJ'
{
  "dashboard": {
    "title": "🧠 Neural Network - Server Components",
    "description": "Representação neural dos componentes do servidor homelab",
    "tags": ["neural", "infrastructure", "monitoring"],
    "timezone": "browser",
    "refresh": "30s",
    "schemaVersion": 38,
    "version": 0,
    "uid": "neural-network-v1",
    "panels": [
      {
        "id": 1,
        "title": "🌐 Central - Status da Rede Neural",
        "type": "stat",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
        "targets": [
          {
            "refId": "A",
            "expr": "count(up == 1)",
            "legendFormat": "Serviços Ativos"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "background",
          "reduceOptions": {"values": false, "calcs": ["lastNotNull"]}
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 10},
                {"color": "green", "value": 15}
              ]
            }
          }
        }
      },
      {
        "id": 2,
        "title": "🐳 Containers - Memory (MB)",
        "type": "piechart",
        "gridPos": {"h": 10, "w": 12, "x": 0, "y": 8},
        "targets": [
          {
            "refId": "A",
            "expr": "container_memory_usage_bytes / 1024 / 1024",
            "legendFormat": "{{name}}"
          }
        ],
        "options": {
          "legend": {"displayMode": "list", "placement": "right"},
          "tooltip": {"mode": "single"},
          "displayLabels": ["name", "value"]
        },
        "fieldConfig": {"defaults": {"unit": "MB"}}
      },
      {
        "id": 3,
        "title": "🤖 Agentes - Status",
        "type": "table",
        "gridPos": {"h": 10, "w": 12, "x": 12, "y": 8},
        "targets": [
          {
            "refId": "A",
            "expr": "up > 0",
            "format": "table",
            "instant": true
          }
        ]
      },
      {
        "id": 4,
        "title": "💾 CPU - Neural Layer 1",
        "type": "graph",
        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 18},
        "targets": [
          {
            "refId": "A",
            "expr": "100 - (avg(irate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)",
            "legendFormat": "CPU %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 60},
                {"color": "red", "value": 85}
              ]
            }
          }
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
      },
      {
        "id": 5,
        "title": "🧠 Memory - Neural Layer 2",
        "type": "graph",
        "gridPos": {"h": 8, "w": 8, "x": 8, "y": 18},
        "targets": [
          {
            "refId": "A",
            "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "legendFormat": "Memory %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 70},
                {"color": "red", "value": 90}
              ]
            }
          }
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
      },
      {
        "id": 6,
        "title": "💿 Disk - Neural Layer 3",
        "type": "graph",
        "gridPos": {"h": 8, "w": 8, "x": 16, "y": 18},
        "targets": [
          {
            "refId": "A",
            "expr": "(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100",
            "legendFormat": "{{device}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 75},
                {"color": "red", "value": 90}
              ]
            }
          }
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
      },
      {
        "id": 7,
        "title": "🌐 Network - Synapses Input/Output",
        "type": "graph",
        "gridPos": {"h": 10, "w": 12, "x": 0, "y": 26},
        "targets": [
          {
            "refId": "A",
            "expr": "rate(node_network_receive_bytes_total[5m]) / 1024",
            "legendFormat": "RX {{device}}"
          },
          {
            "refId": "B",
            "expr": "rate(node_network_transmit_bytes_total[5m]) / 1024",
            "legendFormat": "TX {{device}}"
          }
        ],
        "fieldConfig": {"defaults": {"unit": "KB/s"}},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
      },
      {
        "id": 8,
        "title": "📦 Docker Network - Container Synapses",
        "type": "graph",
        "gridPos": {"h": 10, "w": 12, "x": 12, "y": 26},
        "targets": [
          {
            "refId": "A",
            "expr": "rate(container_network_receive_bytes_total[5m]) / 1024",
            "legendFormat": "RX {{name}}"
          },
          {
            "refId": "B",
            "expr": "rate(container_network_transmit_bytes_total[5m]) / 1024",
            "legendFormat": "TX {{name}}"
          }
        ],
        "fieldConfig": {"defaults": {"unit": "KB/s"}},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
      }
    ],
    "templating": {"list": []},
    "refresh": "30s",
    "time": {"from": "now-1h", "to": "now"}
  },
  "overwrite": true
}
EOFJ

echo "🧠 Criando Dashboard Neural no Grafana..."
echo "📍 Dashboard: Neural Network - Server Components"
echo

# Criar dashboard via API HTTP
echo "⚙️  Enviando dashboard para Grafana..."

RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d @"$DASHBOARD_FILE" \
  http://localhost:3002/api/dashboards/db)

echo "$RESPONSE" | grep -q "\"id\":" && {
  echo "✅ Dashboard criado com sucesso!"
  DASHBOARD_URL=$(echo "$RESPONSE" | grep -o '"url":"[^"]*' | cut -d'"' -f4)
  DASHBOARD_ID=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | cut -d':' -f2)
  echo "📊 Dashboard ID: $DASHBOARD_ID"
  echo "📍 URL: http://localhost:3002$DASHBOARD_URL"
  exit 0
} || {
  echo "⚠️  Resposta do Grafana:"
  echo "$RESPONSE" | head -20
  exit 1
}
