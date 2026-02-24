#!/usr/bin/env python3
"""
Diagnóstico e correção de gauges sem dados no Eddie Central Dashboard
"""

import requests
import json

PROMETHEUS_URL = "http://192.168.15.2:9090"

class GaugeFixPlanner:
    def __init__(self):
        self.critical_missing = []
        self.missing_queries = []
        
    def check_prometheus_metrics(self):
        """Verifica quais métricas existem no Prometheus"""
        print("\n🔍 Verificando métricas no Prometheus...\n")
        
        # Métricas críticas que deveriam existir
        critical_metrics = [
            "agent_count_total",
            "message_rate_total",
            "conversation_count_total",
            "active_conversations_total",
            "agent_memory_decisions_total",
            "ipc_pending_requests",
            "agent_confidence_score",
            "agent_feedback_score"
        ]
        
        for metric in critical_metrics:
            exists = self._check_metric_exists(metric)
            status = "✅" if exists else "❌"
            print(f"{status} {metric}")
            
            if not exists:
                self.critical_missing.append(metric)
    
    def _check_metric_exists(self, metric_name):
        """Verifica se métrica existe no Prometheus"""
        try:
            url = f"{PROMETHEUS_URL}/api/v1/query"
            response = requests.get(url, params={"query": metric_name}, timeout=5)
            result = response.json()
            
            if result.get("status") == "success":
                data = result.get("data", {}).get("result", [])
                return len(data) > 0
            return False
        except Exception as e:
            print(f"   ⚠️ Erro ao verificar: {e}")
            return False
    
    def generate_fix_plan(self):
        """Gera plano de correção"""
        print("\n" + "="*80)
        print("🔧 PLANO DE CORREÇÃO — GAUGES SEM DADOS")
        print("="*80)
        
        if self.critical_missing:
            print(f"\n🔴 MÉTRICAS FALTANDO NO PROMETHEUS ({len(self.critical_missing)}):")
            print("-"*80)
            
            for i, metric in enumerate(self.critical_missing, 1):
                self._print_metric_fix(metric, i)
        else:
            print("\n✅ Todas as métricas básicas existem no Prometheus!")
        
        print("\n⚪ PAINÉIS SEM QUERY CONFIGURADA (11):")
        print("-"*80)
        self._print_query_fixes()
    
    def _print_metric_fix(self, metric, num):
        """Mostra como adicionar uma métrica"""
        fixes = {
            "agent_count_total": {
                "file": "specialized_agents/agent_manager.py",
                "description": "Contar agentes ativos por linguagem",
                "code": """from prometheus_client import Gauge

agents_gauge = Gauge('agent_count_total', 'Agentes ativos', ['language'])

def _update_agent_count(self):
    by_lang = {}
    for agent in self.agents.values():
        lang = agent.language
        by_lang[lang] = by_lang.get(lang, 0) + 1
    
    for lang, count in by_lang.items():
        agents_gauge.labels(language=lang).set(count)
"""
            },
            "message_rate_total": {
                "file": "specialized_agents/agent_interceptor.py",
                "description": "Contar mensagens processadas",
                "code": """from prometheus_client import Counter

msg_counter = Counter('message_rate_total', 'Mensagens totais', ['type', 'status'])

def publish(self, ...):
    try:
        # ... código existente ...
        msg_counter.labels(type=message_type, status='success').inc()
    except Exception as e:
        msg_counter.labels(type=message_type, status='error').inc()
        raise
"""
            },
            "conversation_count_total": {
                "file": "specialized_agents/agent_interceptor.py",
                "description": "Contar conversas por tipo de agente",
                "code": """from prometheus_client import Gauge

conv_gauge = Gauge('conversation_count_total', 'Conversas totais', ['agent_type'])

def track_conversation(self, agent_type, ...):
    # Incrementar contador
    conv_gauge.labels(agent_type=agent_type).inc()
"""
            }
        }
        
        fix = fixes.get(metric, {})
        print(f"\n{num}. {metric}")
        print(f"   📁 Arquivo: {fix.get('file', 'N/A')}")
        print(f"   📝 Descrição: {fix.get('description', 'N/A')}")
        print(f"   💻 Código:\n{fix.get('code', '      # Ver documentação')}")
    
    def _print_query_fixes(self):
        """Mostra queries para painéis sem configuração"""
        queries = {
            "Copilot — Atendimentos 24h (ID: 409)": 
                "sum(increase(conversation_count_total{agent_type=\"copilot\"}[24h]))",
            
            "Copilot — Total Acumulado (ID: 410)":
                "sum(conversation_count_total{agent_type=\"copilot\"})",
            
            "Agentes Locais — Atendimentos 24h (ID: 411)":
                "sum(increase(conversation_count_total{agent_type!=\"copilot\"}[24h]))",
            
            "Agentes Locais — Total Acumulado (ID: 412)":
                "sum(conversation_count_total{agent_type!=\"copilot\"})",
            
            "Total Mensagens (ID: 13)":
                "sum(message_rate_total)",
            
            "Conversas (ID: 14)":
                "sum(active_conversations_total)",
            
            "Conversas (24h) (ID: 406)":
                "sum(increase(conversation_count_total[24h]))",
            
            "Decisões (Memória) (ID: 15)":
                "sum(agent_memory_decisions_total)",
            
            "IPC Pendentes (ID: 16)":
                "sum(ipc_pending_requests)",
            
            "Confiança Média (ID: 26)":
                "avg(agent_confidence_score)",
            
            "Feedback Médio (ID: 27)":
                "avg(agent_feedback_score)"
        }
        
        for title, query in queries.items():
            print(f"\n📊 {title}")
            print(f"   PromQL: {query}")


if __name__ == "__main__":
    planner = GaugeFixPlanner()
    planner.check_prometheus_metrics()
    planner.generate_fix_plan()
