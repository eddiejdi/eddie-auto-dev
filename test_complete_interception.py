#!/usr/bin/env python3
"""Teste detalhado de captura de conversa."""

import sys

sys.path.insert(0, "/home/eddie/myClaude")

from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)
import time
import requests

bus = get_communication_bus()

print("=" * 70)
print("TESTE COMPLETO DE CAPTURA DE CONVERSA")
print("=" * 70)
print()

# Simular conversa realista
print("📨 Simulando conversa de agentes...")
print()

agents = ["PythonAgent", "TestAgent", "OperationsAgent"]
conversation_id = "demo-conv-001"

messages = [
    (MessageType.TASK_START, "Iniciando implementação de novo feature"),
    (MessageType.ANALYSIS, "Analisando requisitos e estrutura existente"),
    (MessageType.REQUEST, "Solicitando análise de compatibilidade"),
    (MessageType.CODE_GEN, "Gerando código para nova funcionalidade"),
    (MessageType.TEST_GEN, "Criando testes unitários"),
    (MessageType.EXECUTION, "Executando suite de testes"),
    (MessageType.TASK_END, "Implementação concluída com sucesso"),
]

for i, (msg_type, content) in enumerate(messages):
    source = agents[i % len(agents)]
    target = agents[(i + 1) % len(agents)] if i < len(messages) - 1 else "all"

    print(f"  [{i + 1}] {source} → {target}: {content}")
    bus.publish(
        message_type=msg_type,
        source=source,
        target=target,
        content=content,
        metadata={
            "conversation_id": conversation_id,
            "iteration": i,
            "project": "interceptor-demo",
        },
    )
    time.sleep(0.3)

print()
print("✅ Conversa enviada para o bus")
print()
time.sleep(2)

# Verificar conversas ativas
print("=" * 70)
print("CONVERSAS ATIVAS")
print("=" * 70)
response = requests.get("http://localhost:8503/interceptor/conversations/active")
data = response.json()

if data.get("count", 0) > 0:
    print(f"✓ {data['count']} conversa(s) ativa(s):\n")
    for conv in data.get("conversations", []):
        print(f"  ID: {conv.get('id')}")
        print(f"  Status: {conv.get('phase')}")
        print(f"  Participants: {', '.join(conv.get('participants', []))}")
        print(f"  Mensagens: {conv.get('message_count')}")
        print(f"  Duração: {conv.get('duration_seconds', 0):.2f}s")

        # Obter detalhes da conversa
        print("\n  Mensagens capturadas:")
        msg_response = requests.get(
            f"http://localhost:8503/interceptor/conversations/{conv.get('id')}/messages"
        )
        if msg_response.status_code == 200:
            messages_data = msg_response.json()
            for msg in messages_data.get("messages", [])[:5]:  # Mostrar primeiras 5
                print(
                    f"    - [{msg.get('type')}] {msg.get('source')} → {msg.get('target')}: {msg.get('content', '')[:50]}"
                )
        print()
else:
    print("⚠️  Nenhuma conversa ativa")

# Verificar estatísticas
print("=" * 70)
print("ESTATÍSTICAS")
print("=" * 70)
stats = requests.get("http://localhost:8503/interceptor/stats").json()
print(f"Total de conversas: {stats['interceptor']['total_conversations']}")
print(f"Conversas ativas: {stats['interceptor']['active_conversations']}")
print(
    f"Total de mensagens interceptadas: {stats['interceptor']['total_messages_intercepted']}"
)
print(f"Uptime: {stats['interceptor']['uptime_seconds']:.1f}s")

print()
print("=" * 70)
print("✅ TESTE COMPLETO FINALIZADO")
print("=" * 70)
