#!/usr/bin/env python3
"""
Add GPU monitoring panels to the Shared Central Grafana dashboard.
Targets: nvidia_gpu_exporter metrics from dual-GPU homelab.
"""
import json
import sys
import shutil
from datetime import datetime

DASHBOARD_FILE = "/home/edenilson/shared-auto-dev/shared-central-clean.json"
DATASOURCE = {"uid": "dfc0w4yioe4u8e", "type": "prometheus"}

# GPU UUIDs from nvidia_gpu_exporter
RTX_2060_UUID = "6ba33090-c1ea-a939-7ac4-a7d7c6b4ba32"
GTX_1050_UUID = "29e83e3f-86ab-1f75-02ce-0a08285f970f"

# Row position: insert after Infraestrutura row (y=0, h=1) and first row panels (y=1, h=6)
# Current y=7 is Shared Agents row. We'll insert GPU row at y=7 and shift everything else down.
GPU_ROW_Y = 7
GPU_PANELS_Y = 8     # panels start at y=8
GPU_PANEL_HEIGHT = 7  # each panel row is 7 units tall
GPU_TOTAL_HEIGHT = 1 + 7 + 7  # row(1) + gauges(7) + timeseries(7) = 15

def make_gpu_panels():
    """Create GPU monitoring panels."""
    panels = []
    
    # --- GPU Row Header ---
    panels.append({
        "id": 500,
        "type": "row",
        "title": "\U0001f3ae GPU Monitoring (Dual NVIDIA)",
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": GPU_ROW_Y},
        "collapsed": False
    })
    
    # --- Row 1: Gauges (y=8) ---
    
    # 1. GPU0 Temperature (RTX 2060 SUPER)
    panels.append({
        "id": 501,
        "type": "gauge",
        "title": "🌡️ RTX 2060 SUPER Temp",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 0, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "celsius",
                "min": 0,
                "max": 100,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 60, "color": "yellow"},
                        {"value": 80, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"}
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "targets": [{
            "expr": f'nvidia_smi_temperature_gpu{{uuid="{RTX_2060_UUID}"}}',
            "legendFormat": "RTX 2060S",
            "refId": "A",
            "datasource": DATASOURCE
        }]
    })
    
    # 2. GPU1 Temperature (GTX 1050)
    panels.append({
        "id": 502,
        "type": "gauge",
        "title": "🌡️ GTX 1050 Temp",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 4, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "celsius",
                "min": 0,
                "max": 100,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 60, "color": "yellow"},
                        {"value": 80, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"}
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "targets": [{
            "expr": f'nvidia_smi_temperature_gpu{{uuid="{GTX_1050_UUID}"}}',
            "legendFormat": "GTX 1050",
            "refId": "A",
            "datasource": DATASOURCE
        }]
    })
    
    # 3. RTX 2060 VRAM Usage (gauge)
    panels.append({
        "id": 503,
        "type": "gauge",
        "title": "💾 RTX 2060 VRAM",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 8, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "percentunit",
                "min": 0,
                "max": 1,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 0.7, "color": "yellow"},
                        {"value": 0.9, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"}
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "targets": [{
            "expr": f'nvidia_smi_memory_used_bytes{{uuid="{RTX_2060_UUID}"}} / nvidia_smi_memory_total_bytes{{uuid="{RTX_2060_UUID}"}}',
            "legendFormat": "VRAM RTX 2060S (8GB)",
            "refId": "A",
            "datasource": DATASOURCE
        }]
    })
    
    # 4. GTX 1050 VRAM Usage (gauge)
    panels.append({
        "id": 504,
        "type": "gauge",
        "title": "💾 GTX 1050 VRAM",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 12, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "percentunit",
                "min": 0,
                "max": 1,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 0.7, "color": "yellow"},
                        {"value": 0.9, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"}
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "targets": [{
            "expr": f'nvidia_smi_memory_used_bytes{{uuid="{GTX_1050_UUID}"}} / nvidia_smi_memory_total_bytes{{uuid="{GTX_1050_UUID}"}}',
            "legendFormat": "VRAM GTX 1050 (2GB)",
            "refId": "A",
            "datasource": DATASOURCE
        }]
    })
    
    # 5. GPU Utilization (both GPUs - stat)
    panels.append({
        "id": 505,
        "type": "stat",
        "title": "⚡ GPU Utilização",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 16, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "percentunit",
                "min": 0,
                "max": 1,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 0.7, "color": "yellow"},
                        {"value": 0.9, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"},
                "mappings": []
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "textMode": "auto",
            "colorMode": "background",
            "graphMode": "area"
        },
        "targets": [
            {
                "expr": f'nvidia_smi_utilization_gpu_ratio{{uuid="{RTX_2060_UUID}"}}',
                "legendFormat": "RTX 2060S",
                "refId": "A",
                "datasource": DATASOURCE
            },
            {
                "expr": f'nvidia_smi_utilization_gpu_ratio{{uuid="{GTX_1050_UUID}"}}',
                "legendFormat": "GTX 1050",
                "refId": "B",
                "datasource": DATASOURCE
            }
        ]
    })
    
    # 6. Power Draw (RTX 2060 - only one with power data)
    panels.append({
        "id": 506,
        "type": "stat",
        "title": "🔌 RTX 2060 Power",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 4, "x": 20, "y": GPU_PANELS_Y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "watt",
                "min": 0,
                "max": 175,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"value": None, "color": "green"},
                        {"value": 100, "color": "yellow"},
                        {"value": 150, "color": "red"}
                    ]
                },
                "color": {"mode": "thresholds"},
                "mappings": []
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "textMode": "auto",
            "colorMode": "background",
            "graphMode": "area"
        },
        "targets": [{
            "expr": f'nvidia_smi_power_draw_watts{{uuid="{RTX_2060_UUID}"}}',
            "legendFormat": "Power RTX 2060S",
            "refId": "A",
            "datasource": DATASOURCE
        }]
    })
    
    # --- Row 2: Timeseries (y=15) ---
    ts_y = GPU_PANELS_Y + GPU_PANEL_HEIGHT  # 8 + 7 = 15
    
    # 7. VRAM Usage Over Time (timeseries - both GPUs in bytes)
    panels.append({
        "id": 507,
        "type": "timeseries",
        "title": "💾 VRAM Usage Over Time",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 12, "x": 0, "y": ts_y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "unit": "bytes",
                "custom": {
                    "lineWidth": 2,
                    "fillOpacity": 20,
                    "gradientMode": "scheme",
                    "showPoints": "never",
                    "spanNulls": True
                },
                "color": {"mode": "palette-classic"}
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "RTX 2060S (8GB)"},
                    "properties": [{"id": "color", "value": {"fixedColor": "green", "mode": "fixed"}}]
                },
                {
                    "matcher": {"id": "byName", "options": "GTX 1050 (2GB)"},
                    "properties": [{"id": "color", "value": {"fixedColor": "blue", "mode": "fixed"}}]
                }
            ]
        },
        "options": {
            "legend": {"calcs": ["lastNotNull", "max"], "displayMode": "table", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"}
        },
        "targets": [
            {
                "expr": f'nvidia_smi_memory_used_bytes{{uuid="{RTX_2060_UUID}"}}',
                "legendFormat": "RTX 2060S (8GB)",
                "refId": "A",
                "datasource": DATASOURCE
            },
            {
                "expr": f'nvidia_smi_memory_used_bytes{{uuid="{GTX_1050_UUID}"}}',
                "legendFormat": "GTX 1050 (2GB)",
                "refId": "B",
                "datasource": DATASOURCE
            }
        ]
    })
    
    # 8. GPU Temperature + Power Over Time
    panels.append({
        "id": 508,
        "type": "timeseries",
        "title": "🌡️ GPU Temperature & Power History",
        "gridPos": {"h": GPU_PANEL_HEIGHT, "w": 12, "x": 12, "y": ts_y},
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "lineWidth": 2,
                    "fillOpacity": 10,
                    "gradientMode": "scheme",
                    "showPoints": "never",
                    "spanNulls": True,
                    "axisPlacement": "auto"
                },
                "color": {"mode": "palette-classic"}
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "RTX 2060S Temp"},
                    "properties": [
                        {"id": "color", "value": {"fixedColor": "orange", "mode": "fixed"}},
                        {"id": "unit", "value": "celsius"}
                    ]
                },
                {
                    "matcher": {"id": "byName", "options": "GTX 1050 Temp"},
                    "properties": [
                        {"id": "color", "value": {"fixedColor": "yellow", "mode": "fixed"}},
                        {"id": "unit", "value": "celsius"}
                    ]
                },
                {
                    "matcher": {"id": "byName", "options": "RTX 2060S Power"},
                    "properties": [
                        {"id": "color", "value": {"fixedColor": "red", "mode": "fixed"}},
                        {"id": "unit", "value": "watt"},
                        {"id": "custom.axisPlacement", "value": "right"}
                    ]
                }
            ]
        },
        "options": {
            "legend": {"calcs": ["lastNotNull", "max", "min"], "displayMode": "table", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"}
        },
        "targets": [
            {
                "expr": f'nvidia_smi_temperature_gpu{{uuid="{RTX_2060_UUID}"}}',
                "legendFormat": "RTX 2060S Temp",
                "refId": "A",
                "datasource": DATASOURCE
            },
            {
                "expr": f'nvidia_smi_temperature_gpu{{uuid="{GTX_1050_UUID}"}}',
                "legendFormat": "GTX 1050 Temp",
                "refId": "B",
                "datasource": DATASOURCE
            },
            {
                "expr": f'nvidia_smi_power_draw_watts{{uuid="{RTX_2060_UUID}"}}',
                "legendFormat": "RTX 2060S Power",
                "refId": "C",
                "datasource": DATASOURCE
            }
        ]
    })
    
    return panels


def main():
    # Backup
    backup_path = f"{DASHBOARD_FILE}.bak.{datetime.now().strftime('%Y%m%d%H%M')}"
    shutil.copy2(DASHBOARD_FILE, backup_path)
    print(f"✅ Backup: {backup_path}")
    
    # Load
    with open(DASHBOARD_FILE) as f:
        dashboard = json.load(f)
    
    panels = dashboard["panels"]
    print(f"📊 Panels antes: {len(panels)}")
    
    # Shift all panels with y >= GPU_ROW_Y down by GPU_TOTAL_HEIGHT
    for p in panels:
        gp = p.get("gridPos", {})
        if gp.get("y", 0) >= GPU_ROW_Y:
            gp["y"] = gp["y"] + GPU_TOTAL_HEIGHT
    
    # Insert GPU panels
    gpu_panels = make_gpu_panels()
    
    # Find insertion point (after infrastructure row panels)
    insert_idx = 0
    for i, p in enumerate(panels):
        gp = p.get("gridPos", {})
        # All original panels at y>=7 (now shifted) come after; we want to insert before them
        if gp.get("y", 0) >= GPU_ROW_Y + GPU_TOTAL_HEIGHT:
            insert_idx = i
            break
    else:
        insert_idx = len(panels)
    
    # Insert GPU panels at the found position
    for i, gp in enumerate(gpu_panels):
        panels.insert(insert_idx + i, gp)
    
    print(f"📊 Panels depois: {len(panels)}")
    print(f"✅ {len(gpu_panels)} GPU panels adicionados")
    
    # Save
    with open(DASHBOARD_FILE, "w") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Dashboard salvo: {DASHBOARD_FILE}")
    print()
    print("GPU panels adicionados:")
    for p in gpu_panels:
        gp = p.get("gridPos", {})
        print(f"  id={p['id']} y={gp['y']} type={p['type']:<12} title={p['title']}")


if __name__ == "__main__":
    main()
