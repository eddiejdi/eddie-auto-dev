#!/usr/bin/env python3
"""
Atualizar os painéis do Grafana com queries PromQL — FASE 2
Adiciona as 11 queries faltantes para completar o dashboard Shared Central
"""
import os
import json
import sys
import requests
from typing import Optional

# Configuração
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://192.168.15.2:3002")  # Local homelab
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY", "")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASS = os.getenv("GRAFANA_PASS", "GrafanaEddie2026")
DASHBOARD_UID = "shared-central"
PROMETHEUS_DS_NAME = "Prometheus"  # Nome da datasource no Grafana

# Queries a adicionar — FASE 2
PHASE2_QUERIES = {
    # ID: (title, query)
    406: ("Conversas (24h)", 'increase(conversations_total[24h])'),
    409: ("🤖 Copilot — Atendimentos 24h", 'increase(copilot_interactions_total[24h])'),
    410: ("🤖 Copilot — Total Acumulado", 'copilot_interactions_total'),
    411: ("⚙️ Agentes Locais — Atendimentos 24h", 'increase(local_agents_interactions_total[24h])'),
    412: ("⚙️ Agentes Locais — Total Acumulado", 'local_agents_interactions_total'),
    13: ("Total Mensagens", 'messages_total'),
    14: ("Conversas", 'conversations_total'),
    15: ("Decisões (Memória)", 'agent_decisions_total'),
    16: ("IPC Pendentes", 'ipc_pending_requests'),
    26: ("Confiança Média", 'avg(agent_decision_confidence)'),
    27: ("Feedback Médio", 'avg(agent_decision_feedback)'),
}

def get_headers() -> dict:
    """Retorna headers para requisições ao Grafana"""
    headers = {
        "Content-Type": "application/json",
    }
    if GRAFANA_API_KEY:
        headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
    return headers

def get_auth() -> tuple:
    """Retorna tuple (user, pass) para Basic Auth"""
    if GRAFANA_API_KEY:
        return None
    return (GRAFANA_USER, GRAFANA_PASS)

def get_dashboard() -> Optional[dict]:
    """Obter dashboard Shared Central"""
    try:
        url = f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}"
        response = requests.get(url, headers=get_headers(), auth=get_auth(), timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao obter dashboard: {e}")
        return None

def get_datasource_id() -> Optional[int]:
    """Obter ID da datasource Prometheus"""
    try:
        url = f"{GRAFANA_URL}/api/datasources"
        response = requests.get(url, headers=get_headers(), auth=get_auth(), timeout=10, verify=False)
        response.raise_for_status()
        
        for ds in response.json():
            if ds.get("name") == PROMETHEUS_DS_NAME:
                return ds.get("id")
        
        print(f"⚠️  Datasource '{PROMETHEUS_DS_NAME}' não encontrada")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao obter datasources: {e}")
        return None

def update_panel_query(panel_id: int, query: str, ds_id: int) -> bool:
    """Atualizar query de um painel"""
    try:
        dashboard = get_dashboard()
        if not dashboard:
            return False
        
        panel_data = dashboard.get("dashboard")
        if not panel_data:
            return False
        
        # Procurar painel por ID
        target_panel = None
        for panel in panel_data.get("panels", []):
            if panel.get("id") == panel_id:
                target_panel = panel
                break
        
        if not target_panel:
            print(f"  ⚠️  Painel {panel_id} não encontrado no dashboard")
            return False
        
        # Atualizar targets do painel
        if "targets" not in target_panel:
            target_panel["targets"] = []
        
        # Remover targets antigos
        target_panel["targets"] = []
        
        # Adicionar novo target
        target_panel["targets"].append({
            "refId": "A",
            "datasourceUid": str(ds_id),
            "expr": query,
            "interval": "",
            "legendFormat": ""
        })
        
        # Fazer update do dashboard
        url = f"{GRAFANA_URL}/api/dashboards/db"
        payload = {
            "dashboard": panel_data,
            "overwrite": True
        }
        
        response = requests.post(url, json=payload, headers=get_headers(), auth=get_auth(), timeout=30, verify=False)
        response.raise_for_status()
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Erro: {e}")
        return False

def main():
    """Entry point"""
    global GRAFANA_API_KEY, GRAFANA_USER, GRAFANA_PASS
    print("🚀 ATUALIZAR PAINÉIS — FASE 2")
    print("=" * 80)
    
    # Verificar credenciais
    if not GRAFANA_API_KEY and (not GRAFANA_USER or not GRAFANA_PASS):
        print("\n⚠️  Credenciais não configuradas!")
        print("   Use uma das opções:")
        print("   1. Exportar: export GRAFANA_API_KEY='seu_token_aqui'")
        print("   2. Exportar: export GRAFANA_USER='admin' GRAFANA_PASS='senha'")
        
        user_input = input("\n📝 Forneça GRAFANA_USER (ou Enter para pular): ").strip()
        if user_input:
            GRAFANA_USER = user_input
            GRAFANA_PASS = input("📝 Forneça GRAFANA_PASS: ").strip()
        else:
            print("\n⚠️  Sem credenciais, tentaremos com credenciais padrão local")
    
    print(f"\n📊 Dashboard: {DASHBOARD_UID}")
    print(f"🔗 URL: {GRAFANA_URL}")
    print(f"👤 Usuário: {GRAFANA_USER}")
    
    # Verificar conexão
    print("\n🔍 Verificando conectividade...")
    dashboard = get_dashboard()
    if not dashboard:
        print("❌ Não foi possível conectar ao Grafana")
        print("\n💡 Opções:")
        print("   1. Verifique se GRAFANA_URL está correto")
        print("   2. Verifique se GRAFANA_USER/GRAFANA_PASS são válidos")
        print("   3. Verifique conectividade de rede")
        return
    
    print("✅ Conectado ao Grafana")
    
    # Obter datasource ID
    ds_id = get_datasource_id()
    if not ds_id:
        print("❌ Não foi possível obter ID da datasource Prometheus")
        return
    
    print(f"✅ Datasource Prometheus ID: {ds_id}")
    
    # Atualizar painéis FASE 2
    print(f"\n📝 Atualizando {len(PHASE2_QUERIES)} painéis...")
    updated = 0
    
    for panel_id, (title, query) in PHASE2_QUERIES.items():
        print(f"\n  [{panel_id:3d}] {title}")
        print(f"        Query: {query}")
        
        if update_panel_query(panel_id, query, ds_id):
            print(f"        ✅ Atualizado")
            updated += 1
        else:
            print(f"        ❌ Falha")
    
    print(f"\n{'=' * 80}")
    print(f"📊 RESULTADO: {updated}/{len(PHASE2_QUERIES)} painéis atualizados")
    print(f"{'=' * 80}")
    
    if updated > 0:
        print(f"\n✅ Recarregue o Grafana em: {GRAFANA_URL}/d/{DASHBOARD_UID}")
    else:
        print("\n⚠️  Nenhum painel foi atualizado")
        print("    Verifique as credenciais e permissões")

if __name__ == '__main__':
    # Desabilitar SSL warnings
    import urllib3
    urllib3.disable_warnings()
    
    main()
