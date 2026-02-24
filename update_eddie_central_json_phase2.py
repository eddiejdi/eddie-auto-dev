#!/usr/bin/env python3
"""
Atualizar eddie-central.json com queries FASE 2
Modified directly no arquivo provisioned
"""
import json
import sys

EDDIE_CENTRAL_JSON = "/tmp/eddie-central.json"

# Queries a adicionar — FASE 2
PHASE2_QUERIES = {
    # ID painel: (titulo, query_promql)
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

print("=" * 80)
print("🔧 ATUALIZAR eddie-central.json COM QUERIES FASE 2")
print("=" * 80)

# Carregar arquivo
print(f"\n📖 Carregando {EDDIE_CENTRAL_JSON}...")
with open(EDDIE_CENTRAL_JSON, 'r') as f:
    dashboard = json.load(f)

print(f"✅ Dashboard carregado")
print(f"   Título: {dashboard.get('title')}")
print(f"   Painéis: {len(dashboard.get('panels', []))}")

# Atualizar painéis
updated = 0
failed = 0

for panel_id, (title, query) in PHASE2_QUERIES.items():
    print(f"\n[{panel_id:3d}] {title}")
    print(f"      Query: {query}")
    
    # Procurar painel por ID
    target_panel = None
    for panel in dashboard.get("panels", []):
        if panel.get("id") == panel_id:
            target_panel = panel
            break
    
    if not target_panel:
        print(f"      ❌ Painel não encontrado")
        failed += 1
        continue
    
    # Atualizar targets
    if "targets" not in target_panel:
        target_panel["targets"] = []
    
    target_panel["targets"] = []
    target_panel["targets"].append({
        "refId": "A",
        "datasourceUid": "${DS_PROMETHEUS}",  # Referência dinâmica
        "expr": query,
        "interval": "",
        "legendFormat": ""
    })
    
    print(f"      ✅ Query atualizada")
    updated += 1

print(f"\n{'=' * 80}")
print(f"📊 RESUMO: {updated}/{len(PHASE2_QUERIES)} painéis atualizados, {failed} falharam")
print(f"{'=' * 80}")

# Salvar arquivo atualizado
print(f"\n💾 Salvando arquivo atualizado...")
with open(EDDIE_CENTRAL_JSON, 'w') as f:
    json.dump(dashboard, f, indent=2)

print(f"✅ Arquivo salvo: {EDDIE_CENTRAL_JSON}")

# Próximos passos
print(f"\n📝 Próximos passos:")
print(f"   1. Fazer upload do arquivo para homelab:")
print(f"      scp /tmp/eddie-central.json homelab@192.168.15.2:/tmp/")
print(f"      ")
print(f"   2. Substituir no container Grafana:")
print(f"      ssh homelab@192.168.15.2 'docker cp /tmp/eddie-central.json grafana:/etc/grafana/provisioning/dashboards/'")
print(f"      ")
print(f"   3. Recarregar Grafana:")
print(f"      ssh homelab@192.168.15.2 'docker restart grafana'")
print(f"      ")
print(f"   4. Validar:")
print(f"      python3 validate_eddie_central_api.py")
