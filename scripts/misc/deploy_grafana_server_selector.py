#!/usr/bin/env python3
"""
Deploy do seletor de servidores no dashboard Grafana
Adiciona um dropdown para alternar entre servidores (localhost, 192.168.15.2, etc)
"""

import os
import sys
import json
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HOMELAB_HOST = os.getenv("HOMELAB_HOST", "192.168.15.2")
HOMELAB_USER = os.getenv("HOMELAB_USER", "homelab")
HOMELAB_TARGET = f"{HOMELAB_USER}@{HOMELAB_HOST}"
SSH_KEY = os.path.expanduser(os.getenv("HOMELAB_SSH_KEY", "~/.ssh/shared_deploy_rsa"))

GRAFANA_USER = os.getenv("GRAFANA_USER")
GRAFANA_PASS = os.getenv("GRAFANA_PASS")

GRAFANA_URL = "http://localhost:3000"
DASHBOARD_UID = "btc-trading-monitor"

def run_ssh_cmd(cmd: str) -> str:
    """Executa comando no homelab via SSH"""
    try:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, HOMELAB_TARGET, cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"SSH Error: {result.stderr}")
            return ""
        return result.stdout
    except Exception as e:
        print(f"❌ SSH Error: {e}")
        sys.exit(1)

def get_dashboard_via_ssh() -> dict:
    """Obtém dashboard do Grafana via SSH no homelab"""
    print(f"📡 Conectando ao Grafana em {HOMELAB_HOST}...")
    
    # Comando para obter o dashboard via curl no homelab
    cmd = (
        f"curl -s -u {GRAFANA_USER}:{GRAFANA_PASS} "
        f"http://localhost:3000/api/dashboards/uid/{DASHBOARD_UID}"
    )
    
    output = run_ssh_cmd(cmd)
    
    if not output:
        print("❌ Falha ao obter dashboard")
        sys.exit(1)
    
    try:
        data = json.loads(output)
        if "error" in data:
            print(f"❌ Erro do Grafana: {data.get('error')}")
            sys.exit(1)
        return data
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao parsear JSON: {e}")
        print(f"Output: {output[:500]}")
        sys.exit(1)

def add_server_variable(dashboard: dict) -> dict:
    """Adiciona variável 'servidor' ao dashboard"""
    print("🔧 Adicionando seletor de servidores...")
    
    # Asegurar que existe a seção 'templating'
    if "templating" not in dashboard:
        dashboard["templating"] = {"list": []}
    
    # Remover variável de servidor anterior se existir
    dashboard["templating"]["list"] = [
        v for v in dashboard["templating"]["list"] 
        if v.get("name") != "servidor"
    ]
    
    # Adicionar nova variável de servidor
    server_var = {
        "name": "servidor",
        "type": "custom",
        "label": "Servidor",
        "description": "Selecione o servidor para monitorar",
        "current": {
            "selected": False,
            "text": "localhost",
            "value": "localhost"
        },
        "options": [
            {"text": "Localhost", "value": "localhost"},
            {"text": "Homelab (192.168.15.2)", "value": "192.168.15.2"},
            {"text": "Orange Pi (192.168.15.166)", "value": "192.168.15.166"},
            {"text": "NAS (192.168.15.100)", "value": "192.168.15.100"},
        ],
        "multi": False,
        "includeAll": False,
        "sort": 0,
        "show": "label",
        "showLabel": True,
        "showValue": True,
        "isMulti": False
    }
    
    dashboard["templating"]["list"].insert(0, server_var)
    
    print("   ✅ Variável de servidor adicionada")
    print(f"   ✅ Servidores disponíveis: {len(server_var['options'])}")
    
    return dashboard

def update_dashboard_via_ssh(dashboard: dict) -> bool:
    """Atualiza dashboard no Grafana via SSH"""
    print("💾 Salvando dashboard no Grafana...")
    
    # Preparar JSON para envio
    dashboard_data = {"dashboard": dashboard}
    json_payload = json.dumps(dashboard_data)
    
    # Escapar JSON para passar via SSH
    escaped_json = json_payload.replace('"', '\\"').replace("'", "\\'")
    
    # Comando para atualizar dashboard via curl no homelab
    cmd = (
        f"curl -s -X POST "
        f"-u {GRAFANA_USER}:{GRAFANA_PASS} "
        f"-H 'Content-Type: application/json' "
        f"-d '{escaped_json}' "
        f"http://localhost:3000/api/dashboards/db"
    )
    
    output = run_ssh_cmd(cmd)
    
    try:
        result = json.loads(output)
        if "id" in result:
            print(f"   ✅ Dashboard atualizado (ID: {result['id']})")
            if "url" in result:
                print(f"   📍 URL: {result['url']}")
            return True
        elif "error" in result:
            print(f"   ❌ Erro: {result['error']}")
            return False
    except json.JSONDecodeError:
        print(f"   ⚠️  Resposta: {output[:200]}")
        return False
    
    return False

def main():
    print("=" * 60)
    print("🎯 DEPLOY: SELETOR DE SERVIDORES NO GRAFANA")
    print("=" * 60)
    print()
    
    # Validações
    if not GRAFANA_USER or not GRAFANA_PASS:
        print("❌ Erro: GRAFANA_USER e GRAFANA_PASS não configurados")
        sys.exit(1)
    
    # Obter dashboard
    dashboard_data = get_dashboard_via_ssh()
    dashboard = dashboard_data.get("dashboard", {})
    
    if not dashboard:
        print("❌ Dashboard não encontrado")
        sys.exit(1)
    
    print(f"✅ Dashboard obtido: {dashboard.get('title')}")
    print()
    
    # Adicionar seletor de servidor
    dashboard = add_server_variable(dashboard)
    print()
    
    # Atualizar dashboard
    success = update_dashboard_via_ssh(dashboard)
    
    if success:
        print()
        print("=" * 60)
        print("✅ DEPLOY CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print()
        print("🎉 Você agora pode:")
        print("   1. Acessar o Grafana em https://grafana.rpa4all.com")
        print("   2. Clicar no dashboard de trading")
        print("   3. Usar o dropdown 'Servidor' para alternar entre:")
        print("      - localhost")
        print("      - Homelab (192.168.15.2)")
        print("      - Orange Pi (192.168.15.166)")
        print("      - NAS (192.168.15.100)")
        print()
        sys.exit(0)
    else:
        print()
        print("❌ Falha ao atualizar dashboard")
        sys.exit(1)

if __name__ == "__main__":
    main()
