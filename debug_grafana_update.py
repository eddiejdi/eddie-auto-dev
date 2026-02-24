#!/usr/bin/env python3
"""
Debug: Entender erro 400 do Grafana
"""
import requests
import json
import os
import urllib3

urllib3.disable_warnings()

GRAFANA_URL = "http://192.168.15.2:3002"
GRAFANA_USER = "admin"
GRAFANA_PASS = "GrafanaEddie2026"

print("🔍 DEBUG: Investigando erro 400 do Grafana...\n")

# 1. Obter dashboard
print("1️⃣  Obtendo dashboard Eddie Central...")
response = requests.get(
    f"{GRAFANA_URL}/api/dashboards/uid/eddie-central",
    auth=(GRAFANA_USER, GRAFANA_PASS),
    verify=False
)

if response.status_code != 200:
    print(f"❌ Erro ao obter dashboard: {response.status_code}")
    print(response.text[:500])
    exit(1)

dashboard_data = response.json()
print(f"✅ Dashboard obtido")

# 2. Verificar estrutura
dashboard = dashboard_data.get("dashboard", {})
print(f"   - Versão: {dashboard.get('version')}")
print(f"   - Panels: {len(dashboard.get('panels', []))}")
print(f"   - Tags: {dashboard.get('tags', [])}")
print(f"   - Templating: {len(dashboard.get('templating', {}).get('list', []))} variáveis")

# 3. Tentar update com estrutura mínima
print("\n2️⃣  Testando update com estrutura simples...")

# Aumentar versão
dashboard['version'] = dashboard.get('version', 0) + 1

payload = {
    "dashboard": dashboard,
    "overwrite": True,
    "message": "Updated by Eddie Central Metrics Agent"
}

response = requests.post(
    f"{GRAFANA_URL}/api/dashboards/db",
    json=payload,
    auth=(GRAFANA_USER, GRAFANA_PASS),
    headers={"Content-Type": "application/json"},
    verify=False
)

print(f"Status: {response.status_code}")
if response.status_code != 200:
    print(f"Erro: {response.text[:1000]}")
    
    # Tentar entender o erro
    if response.status_code == 400:
        print("\n💡 Erro 400 pode significar:")
        print("   - Missing required fields in dashboard")
        print("   - Invalid panel configuration")
        print("   - Versioning conflict")
        print("   - Title ou UID inválido")
        
        try:
            error_data = response.json()
            print(f"\n   Detalhes: {json.dumps(error_data, indent=2)}")
        except:
            pass
else:
    print("✅ Update bem-sucedido!")
    result = response.json()
    print(f"   ID: {result.get('id')}")
    print(f"   URL: {result.get('url')}")
