#!/usr/bin/env python3
"""
Análise resumida da validação do Eddie Central Dashboard
"""

import json
from datetime import datetime

# Dados consolidados de validação
VALIDATION_RESULTS = {
    "timestamp": "2026-02-24T10:26:33.155451",
    "dashboard": "Eddie Auto-Dev — Central",
    "total_gauges": 20,
    "valid": 7,
    "invalid": 13,
    "success_rate": 35.0,
    
    "gauges_validos": [
        {
            "id": 2,
            "titulo": "Memória",
            "tipo": "gauge",
            "query": "1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
            "valor": "0.2779947845718639",
            "descricao": "Percentual de memória em uso"
        },
        {
            "id": 3,
            "titulo": "Disco /",
            "tipo": "gauge",
            "query": "1 - (node_filesystem_avail_bytes{mountpoint=\"/\",fstype!=\"tmpfs\"} / node_filesystem_size_bytes{mountpoint=\"/\",fstype!=\"tmpfs\"})",
            "valor": "0.8386883906171105",
            "descricao": "Percentual de disco em uso na partição raiz"
        },
        {
            "id": 4,
            "titulo": "Uptime",
            "tipo": "stat",
            "query": "time() - node_boot_time_seconds",
            "valor": "131719.38700008392",
            "descricao": "Tempo desde último boot em segundos (~1.5 dias)"
        },
        {
            "id": 5,
            "titulo": "Targets UP",
            "tipo": "stat",
            "query": "up",
            "valor": "0, 0, 1",
            "descricao": "Status de disponibilidade de targets (0=DOWN, 1=UP)"
        },
        {
            "id": 6,
            "titulo": "RAM Total",
            "tipo": "stat",
            "query": "node_memory_MemTotal_bytes",
            "valor": "33451716608",
            "descricao": "RAM total do sistema em bytes (~31 GB)"
        },
        {
            "id": 8,
            "titulo": "Containers Ativos",
            "tipo": "gauge",
            "query": "count(container_last_seen{name!=\"\"})",
            "valor": "17",
            "descricao": "Quantidade de containers Docker aderenços"
        },
        {
            "id": 10,
            "titulo": "WhatsApp Accuracy (%)",
            "tipo": "gauge",
            "query": "eddie_whatsapp_train_accuracy",
            "valor": "0.92",
            "descricao": "Taxa de acurácia do modelo WhatsApp (92%)"
        }
    ],
    
    "gauges_problematicos": [
        {
            "id": 402,
            "titulo": "Agentes Ativos",
            "tipo": "gauge",
            "query": "agent_count_total",
            "status": "SEM DADOS",
            "problema": "Métrica agent_count_total não existe no Prometheus",
            "solucao": "Verificar se agentes estão exportando métricas corretamente"
        },
        {
            "id": 403,
            "titulo": "Taxa de Mensagens (msgs/s)",
            "tipo": "gauge",
            "query": "message_rate_total",
            "status": "SEM DADOS",
            "problema": "Métrica message_rate_total não existe no Prometheus",
            "solucao": "Verificar se o interceptor de mensagens está rodando e exportando métricas"
        },
        {
            "id": 406,
            "titulo": "Conversas (24h)",
            "tipo": "gauge",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar conversas das últimas 24h"
        },
        {
            "id": 409,
            "titulo": "🤖 Copilot — Atendimentos 24h",
            "tipo": "gauge",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar atendimentos do Copilot"
        },
        {
            "id": 410,
            "titulo": "🤖 Copilot — Total Acumulado",
            "tipo": "gauge",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para total acumulado do Copilot"
        },
        {
            "id": 411,
            "titulo": "⚙️ Agentes Locais — Atendimentos 24h",
            "tipo": "gauge",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar atendimentos de agentes locais"
        },
        {
            "id": 412,
            "titulo": "⚙️ Agentes Locais — Total Acumulado",
            "tipo": "gauge",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para total acumulado de agentes locais"
        },
        {
            "id": 13,
            "titulo": "Total Mensagens",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar total de mensagens"
        },
        {
            "id": 14,
            "titulo": "Conversas",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar conversas"
        },
        {
            "id": 15,
            "titulo": "Decisões (Memória)",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar decisões armazenadas em memória"
        },
        {
            "id": 16,
            "titulo": "IPC Pendentes",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para contar IPC pendentes"
        },
        {
            "id": 26,
            "titulo": "Confiança Média",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para calcular confiança média"
        },
        {
            "id": 27,
            "titulo": "Feedback Médio",
            "tipo": "stat",
            "status": "SEM QUERY",
            "problema": "Painel não possui query Prometheus configurada",
            "solucao": "Adicionar query para calcular feedback médio"
        }
    ]
}

def print_report():
    """Imprime relatório consolidado"""
    
    print("=" * 100)
    print("📊 RELATÓRIO CONSOLIDADO - VALIDAÇÃO DE GAUGES - EDDIE CENTRAL DASHBOARD")
    print("=" * 100)
    print(f"\n🕐 Timestamp: {VALIDATION_RESULTS['timestamp']}")
    print(f"📍 Dashboard: {VALIDATION_RESULTS['dashboard']}")
    print(f"🔗 URL: https://grafana.rpa4all.com/d/eddie-central/eddie-auto-dev-e28094-central?orgId=1&from=now-6h&to=now")
    
    print("\n" + "=" * 100)
    print("📈 RESUMO EXECUTIVO")
    print("=" * 100)
    
    total = VALIDATION_RESULTS["total_gauges"]
    valid = VALIDATION_RESULTS["valid"]
    invalid = VALIDATION_RESULTS["invalid"]
    rate = VALIDATION_RESULTS["success_rate"]
    
    print(f"\n📊 Total de Gauges/Stats: {total}")
    print(f"✅ Funcionais: {valid} ({rate:.1f}%)")
    print(f"❌ Problemáticos: {invalid} ({100-rate:.1f}%)")
    
    print("\n" + "-" * 100)
    print("\n✅ GAUGES VÁLIDOS ({})".format(len(VALIDATION_RESULTS["gauges_validos"])))
    print("-" * 100)
    
    for i, gauge in enumerate(VALIDATION_RESULTS["gauges_validos"], 1):
        print(f"\n{i}. {gauge['titulo']} (ID: {gauge['id']})")
        print(f"   📍 Tipo: {gauge['tipo']}")
        print(f"   📊 Valor: {gauge['valor']}")
        print(f"   📝 Descrição: {gauge['descricao']}")
        print(f"   🔍 Query: {gauge['query'][:80]}...")
    
    print("\n" + "-" * 100)
    print("\n❌ GAUGES COM PROBLEMAS ({})".format(len(VALIDATION_RESULTS["gauges_problematicos"])))
    print("-" * 100)
    
    # Agrupar por tipo de problema
    sem_query = [g for g in VALIDATION_RESULTS["gauges_problematicos"] if g["status"] == "SEM QUERY"]
    sem_dados = [g for g in VALIDATION_RESULTS["gauges_problematicos"] if g["status"] == "SEM DADOS"]
    
    if sem_dados:
        print(f"\n🔴 SEM DADOS NO PROMETHEUS ({len(sem_dados)})")
        print("-" * 100)
        
        for gauge in sem_dados:
            print(f"\n• {gauge['titulo']} (ID: {gauge['id']})")
            print(f"  Query: {gauge['query']}")
            print(f"  ⚠️ Problema: {gauge['problema']}")
            print(f"  ✅ Solução: {gauge['solucao']}")
    
    if sem_query:
        print(f"\n⚪ SEM QUERY CONFIGURADA ({len(sem_query)})")
        print("-" * 100)
        
        for gauge in sem_query:
            print(f"\n• {gauge['titulo']} (ID: {gauge['id']}, Tipo: {gauge['tipo']})")
            print(f"  ⚠️ Problema: {gauge['problema']}")
            print(f"  ✅ Solução: {gauge['solucao']}")
    
    print("\n" + "=" * 100)
    print("🎯 RECOMENDAÇÕES IMEDIATAS")
    print("=" * 100)
    
    print("""
1. ✅ GAUGES FUNCIONAIS - Status OK
   • Sistema de monitoramento base (memória, disco, uptime) operacional
   • Accuracy do WhatsApp model em 92% - adequado
   • 17 containers rodando - sistema distribuído ativo

2. ❌ MÉTRICAS FALTANDO (2 itemns críticos):
   
   a) Agentes Ativos (agent_count_total)
      → Verificar se agentes estão exportando métricas em /metrics
      → Testar: curl http://localhost:8503/metrics | grep agent_count
      → Status: CRÍTICO - Necessário para monitoramento de agentes
   
   b) Taxa de Mensagens (message_rate_total)
      → Verificar se interceptor está rodando
      → Comando: systemctl status specialized-agents-api
      → Status: CRÍTICO - Necessário para observabilidade de fluxo

3. ⚪ PAINÉIS SEM CONFIGURAÇÃO (11 itens):
   
   a) Gauges de Atendimento (Copilot + Agentes Locais)
      → Sem query PromQL definida
      → Status: BLOQUEADO - Need custom queries
   
   b) Stats de Comunicação (Mensagens, Conversas, Confiança)
      → Sem query PromQL definida
      → Status: BLOQUEADO - Need custom queries

4. 🔧 PRÓXIMOS PASSOS:
   
   ① Ativar exportação de métricas faltantes:
      - agent_count_total (Python exporter)
      - message_rate_total (Interceptor exporter)
   
   ② Configurar queries faltantes no Grafana:
      - Dashboard ID: eddie-central
      - Adicionar 11 queries customize com PromQL
   
   ③ Validar saúde de serviços:
      - specialized-agents-api (porta 8503)
      - interceptor de conversas
      - Chrome/browser agentes
    """)
    
    print("=" * 100)
    print(f"\n💾 Relatório detalhado em JSON: /tmp/eddie_central_validation_api.json")
    print(f"📝 Log de execução: /tmp/validation_output.log")
    print("=" * 100)


if __name__ == "__main__":
    print_report()
