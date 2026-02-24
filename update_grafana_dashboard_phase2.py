#!/usr/bin/env python3
"""
Update Grafana Dashboard — FASE 2
Adiciona as PromQL queries para as 11 métricas estendidas

Métricas a adicionar:
1. Conversas (24h) → conversation_count_total
2. Copilot — Atendimentos 24h → active_conversations_total{agent_type="copilot"}
3. Copilot — Total Acumulado → conversation_count_total{agent_type="copilot"}
4. Agentes Locais — Atendimentos 24h → active_conversations_total{agent_type="local_agents"}
5. Agentes Locais — Total Acumulado → conversation_count_total{agent_type="local_agents"}
6. Total Mensagens → message_rate_total (FASE 1) ou sum de todos
7. Conversas → active_conversations_total
8. Decisões (Memória) → agent_memory_decisions_total
9. IPC Pendentes → ipc_pending_requests
10. Confiança Média → agent_confidence_score
11. Feedback Médio → agent_feedback_score
"""

import requests
import json
import sys
import os
from typing import Dict, List, Any

class GrafanaUpdater:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_dashboard(self, uid: str) -> Dict[str, Any]:
        """Obter dashboard por UID"""
        response = requests.get(
            f'{self.url}/api/dashboards/uid/{uid}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def update_dashboard(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Atualizar dashboard"""
        db = dashboard_data['dashboard']
        response = requests.post(
            f'{self.url}/api/dashboards/db',
            headers=self.headers,
            json={
                'dashboard': db,
                'overwrite': True,
                'message': 'FASE 2: Adicionar queries para 11 métricas estendidas'
            }
        )
        response.raise_for_status()
        return response.json()
    
    def find_panel_by_title(self, panels: List[Dict], title: str) -> Dict[str, Any]:
        """Encontrar painel por título"""
        for panel in panels:
            if panel.get('title', '').strip() == title:
                return panel
        return None
    
    def add_query_to_panel(self, panel: Dict[str, Any], promql: str, legend: str = ''):
        """Adicionar PromQL query ao painel"""
        if 'targets' not in panel:
            panel['targets'] = []
        
        # Criar nova query
        new_query = {
            'expr': promql,
            'interval': '',
            'legendFormat': legend,
            'refId': chr(65 + len(panel['targets']))  # A, B, C, etc
        }
        
        panel['targets'].append(new_query)
        return panel

def main():
    # Configuração
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'https://grafana.rpa4all.com')
    GRAFANA_API_KEY = os.environ.get('GRAFANA_API_KEY', '')
    DASHBOARD_UID = 'eddie-central'
    
    if not GRAFANA_API_KEY:
        print("❌ Erro: GRAFANA_API_KEY não configurado")
        print("   export GRAFANA_API_KEY=seu_api_token")
        sys.exit(1)
    
    print("🚀 Atualizar Grafana Dashboard — FASE 2")
    print("=" * 60)
    print(f"URL: {GRAFANA_URL}")
    print(f"Dashboard UID: {DASHBOARD_UID}")
    print()
    
    try:
        updater = GrafanaUpdater(GRAFANA_URL, GRAFANA_API_KEY)
        
        # =========================================================================
        # STEP 1: Obter dashboard atual
        # =========================================================================
        print("1️⃣ Obtendo dashboard...")
        dashboard_data = updater.get_dashboard(DASHBOARD_UID)
        dashboard = dashboard_data['dashboard']
        panels = dashboard.get('panels', [])
        
        print(f"✅ Dashboard obtido: {dashboard.get('title')}")
        print(f"   Total de painéis: {len(panels)}")
        print()
        
        # =========================================================================
        # STEP 2: Definir queries para cada painel
        # =========================================================================
        print("2️⃣ Atualizando queries...")
        
        updates = [
            # Grupo A: Conversas por tipo de agente
            {
                'title': 'Conversas (24h)',
                'promql': 'sum(increase(conversation_count_total[24h]))',
                'legend': 'Total 24h'
            },
            {
                'title': '🤖 Copilot — Atendimentos 24h',
                'promql': 'sum(increase(conversation_count_total{agent_type="copilot"}[24h]))',
                'legend': 'Copilot 24h'
            },
            {
                'title': '🤖 Copilot — Total Acumulado',
                'promql': 'sum(conversation_count_total{agent_type="copilot"})',
                'legend': 'Copilot Total'
            },
            {
                'title': '⚙️ Agentes Locais — Atendimentos 24h',
                'promql': 'sum(increase(conversation_count_total{agent_type="local_agents"}[24h]))',
                'legend': 'Agentes Locais 24h'
            },
            {
                'title': '⚙️ Agentes Locais — Total Acumulado',
                'promql': 'sum(conversation_count_total{agent_type="local_agents"})',
                'legend': 'Agentes Locais Total'
            },
            
            # Grupo B: Métricas de comunicação
            {
                'title': 'Total Mensagens',
                'promql': 'sum(message_rate_total)',
                'legend': 'Total Msgs/s'
            },
            {
                'title': 'Conversas',
                'promql': 'sum(active_conversations_total)',
                'legend': 'Conversas Ativas'
            },
            {
                'title': 'Decisões (Memória)',
                'promql': 'sum(agent_memory_decisions_total)',
                'legend': 'Decisões'
            },
            {
                'title': 'IPC Pendentes',
                'promql': 'sum(ipc_pending_requests)',
                'legend': 'Pendentes'
            },
            {
                'title': 'Confiança Média',
                'promql': 'avg(agent_confidence_score)',
                'legend': 'Confiança'
            },
            {
                'title': 'Feedback Médio',
                'promql': 'avg(agent_feedback_score)',
                'legend': 'Feedback'
            },
        ]
        
        updated_count = 0
        for update_info in updates:
            panel = updater.find_panel_by_title(panels, update_info['title'])
            if panel:
                # Limpar targets antigos se tiverem
                if not panel.get('targets') or len(panel.get('targets', [])) == 0:
                    updater.add_query_to_panel(
                        panel,
                        update_info['promql'],
                        update_info['legend']
                    )
                    updated_count += 1
                    print(f"  ✅ {update_info['title']}")
                    print(f"     Query: {update_info['promql'][:60]}...")
                else:
                    print(f"  ℹ️  {update_info['title']} (já tem query)")
            else:
                print(f"  ❌ {update_info['title']} — Painel não encontrado")
        
        print()
        print(f"✅ {updated_count} painéis atualizados")
        print()
        
        # =========================================================================
        # STEP 3: Salvar dashboard
        # =========================================================================
        print("3️⃣ Salvando dashboard...")
        result = updater.update_dashboard(dashboard_data)
        
        if result.get('status') == 'success':
            print(f"✅ Dashboard atualizado com sucesso!")
            print(f"   ID: {result.get('id')}")
            print(f"   Versão: {result.get('version')}")
        else:
            print(f"❌ Erro ao salvar: {result.get('message', 'Unknown error')}")
            sys.exit(1)
        
        # =========================================================================
        # CONCLUSÃO
        # =========================================================================
        print()
        print("=" * 60)
        print("✅ FASE 2 — GRAFANA ATUALIZADO")
        print("=" * 60)
        print()
        print(f"🔗 Dashboard: {GRAFANA_URL}/d/{DASHBOARD_UID}/")
        print()
        print("📊 Próximos passos:")
        print("  1. Recarregar dashboard no navegador (F5)")
        print("  2. Aguardar dados aparecerem (até 1 minuto)")
        print("  3. Executar: python3 validate_eddie_central_api.py")
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
