#!/usr/bin/env python3
"""
Validação FASE 2 — Verificar se as métricas estendidas estão sendo coletadas
Este script valida diretamente no Prometheus, não precisa de API key do Grafana
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any

class PrometheusValidator:
    def __init__(self, prometheus_url: str = 'http://192.168.15.2:9090'):
        self.url = prometheus_url.rstrip('/')
    
    def query(self, promql: str) -> Dict[str, Any]:
        """Executar query PromQL"""
        try:
            response = requests.get(
                f'{self.url}/api/v1/query',
                params={'query': promql},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Erro ao executar query: {e}")
            return {'status': 'error', 'data': {}}
    
    def get_value(self, result: Dict) -> Any:
        """Extrair valor do resultado PromQL"""
        try:
            if result.get('status') == 'success':
                data = result.get('data', {})
                if data.get('result'):
                    value = data['result'][0].get('value', [None, None])[1]
                    return float(value) if value else None
        except:
            pass
        return None

def main():
    print("=" * 80)
    print("✅ VALIDAÇÃO FASE 2 — Métricas Estendidas")
    print("=" * 80)
    print(f"🕐 Timestamp: {datetime.now().isoformat()}")
    print(f"🔗 Prometheus: http://192.168.15.2:9090")
    print()
    
    validator = PrometheusValidator()
    
    # =========================================================================
    # Métricas a validar
    # =========================================================================
    tests = [
        # FASE 1 (continuação)
        {
            'name': 'Agentes Ativos',
            'promql': 'agent_count_total',
            'panel': 'Agentes Ativos',
            'expected_type': 'gauge'
        },
        {
            'name': 'Taxa de Mensagens (msgs/s)',
            'promql': 'message_rate_total',
            'panel': 'Taxa de Mensagens (msgs/s)',
            'expected_type': 'gauge'
        },
        
        # FASE 2 — Grupo A: Conversas
        {
            'name': 'Conversas 24h (Total)',
            'promql': 'sum(increase(conversation_count_total[24h]))',
            'panel': 'Conversas (24h)',
            'expected_type': 'gauge'
        },
        {
            'name': 'Conversas Copilot 24h',
            'promql': 'sum(increase(conversation_count_total{agent_type="copilot"}[24h]))',
            'panel': '🤖 Copilot — Atendimentos 24h',
            'expected_type': 'gauge'
        },
        {
            'name': 'Conversas Copilot (Total)',
            'promql': 'sum(conversation_count_total{agent_type="copilot"})',
            'panel': '🤖 Copilot — Total Acumulado',
            'expected_type': 'gauge'
        },
        {
            'name': 'Conversas Agentes Locais 24h',
            'promql': 'sum(increase(conversation_count_total{agent_type="local_agents"}[24h]))',
            'panel': '⚙️ Agentes Locais — Atendimentos 24h',
            'expected_type': 'gauge'
        },
        {
            'name': 'Conversas Agentes Locais (Total)',
            'promql': 'sum(conversation_count_total{agent_type="local_agents"})',
            'panel': '⚙️ Agentes Locais — Total Acumulado',
            'expected_type': 'gauge'
        },
        
        # FASE 2 — Grupo B: Métricas de comunicação
        {
            'name': 'Total Mensagens',
            'promql': 'sum(message_rate_total)',
            'panel': 'Total Mensagens',
            'expected_type': 'stat'
        },
        {
            'name': 'Conversas Ativas',
            'promql': 'sum(active_conversations_total)',
            'panel': 'Conversas',
            'expected_type': 'stat'
        },
        {
            'name': 'Decisões em Memória',
            'promql': 'sum(agent_memory_decisions_total)',
            'panel': 'Decisões (Memória)',
            'expected_type': 'stat'
        },
        {
            'name': 'IPC Pendentes',
            'promql': 'sum(ipc_pending_requests)',
            'panel': 'IPC Pendentes',
            'expected_type': 'stat'
        },
        {
            'name': 'Confiança Média',
            'promql': 'avg(agent_confidence_score)',
            'panel': 'Confiança Média',
            'expected_type': 'stat'
        },
        {
            'name': 'Feedback Médio',
            'promql': 'avg(agent_feedback_score)',
            'panel': 'Feedback Médio',
            'expected_type': 'stat'
        },
    ]
    
    # =========================================================================
    # Executar testes
    # =========================================================================
    print("📊 Testando consultas PromQL...")
    print()
    
    valid_count = 0
    invalid_count = 0
    
    for i, test in enumerate(tests, 1):
        result = validator.query(test['promql'])
        value = validator.get_value(result)
        
        # Determinar status
        is_valid = value is not None and result.get('status') == 'success'
        status = "✅" if is_valid else "❌"
        
        if is_valid:
            valid_count += 1
            print(f"{status} [{i:2d}] {test['name']}")
            print(f"       Valor: {value:.4f}")
            print(f"       Panel: {test['panel']}")
        else:
            invalid_count += 1
            print(f"{status} [{i:2d}] {test['name']}")
            print(f"       Panel: {test['panel']}")
            print(f"       Status: {result.get('status', 'unknown')}")
        
        print()
    
    # =========================================================================
    # Resumo
    # =========================================================================
    total = valid_count + invalid_count
    success_rate = (valid_count / total * 100) if total > 0 else 0
    
    print("=" * 80)
    print("📈 RESUMO FINAL — FASE 2")
    print("=" * 80)
    print()
    print(f"Total de métricas testadas: {total}")
    print(f"✅ Válidas (com dados): {valid_count}")
    print(f"❌ Inválidas (sem dados): {invalid_count}")
    print(f"📊 Taxa de sucesso: {success_rate:.1f}%")
    print()
    
    # =========================================================================
    # Recomendações
    # =========================================================================
    print("🎯 Recomendações:")
    print()
    
    if valid_count >= 11:
        print("✅ FASE 2 COMPLETA! Todas as 11 métricas estendidas estão sendo coletadas.")
        print("")
        print("Próximos passos:")
        print("  1. Atualizar Grafana dashboard com as queries PromQL")
        print("  2. Aguardar 1 minuto para visualização dos dados")
        print("  3. Validar no dashboard: https://grafana.rpa4all.com/d/eddie-central/")
    elif valid_count >= 6:
        print(f"⚠️  Progresso: {valid_count}/11 métricas implementadas")
        print("")
        print("Ações necessárias:")
        if invalid_count > 0:
            print(f"  • {invalid_count} métrica(s) ainda não respondendo")
            print("  • Verificar logs dos exporters: ")
            print("    - FASE 1: ssh homelab@192.168.15.2 'sudo journalctl -u eddie-central-metrics -n 20'")
            print("    - FASE 2: ssh homelab@192.168.15.2 'sudo journalctl -u eddie-central-extended-metrics -n 20'")
    else:
        print("❌ Falha geral: Múltiplas métricas sem dados")
        print("")
        print("Ações necessárias:")
        print("  1. Verificar status dos serviços no homelab:")
        print("     ssh homelab@192.168.15.2 'sudo systemctl status eddie-central-*'")
        print("  2. Verificar logs do Prometheus:")
        print("     ssh homelab@192.168.15.2 'sudo journalctl -u prometheus -n 50'")
        print("  3. Validar conectividade do Prometheus com exporters:")
        print("     ssh homelab@192.168.15.2 'curl http://localhost:9105/metrics'")
        print("     ssh homelab@192.168.15.2 'curl http://localhost:9106/metrics'")
    
    print()
    print("=" * 80)
    
    # Return exit code
    return 0 if valid_count >= 11 else 1

if __name__ == '__main__':
    exit(main())
