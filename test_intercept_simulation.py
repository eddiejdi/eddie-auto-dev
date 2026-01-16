#!/usr/bin/env python3
"""Simula uma conversa de agentes para testar o interceptador."""
import sys
sys.path.insert(0, '/home/eddie/myClaude')

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
import time
import json

bus = get_communication_bus()

print("📨 Simulando conversa de agentes...")
print()

# Simular uma conversa
agents = ["PythonAgent", "TestAgent", "OperationsAgent"]
conversation_id = "test-conv-001"

messages = [
    {"type": MessageType.TASK_START, "content": "Iniciando análise de requisitos"},
    {"type": MessageType.ANALYSIS, "content": "Analisando estrutura do código"},
    {"type": MessageType.REQUEST, "content": "Planejando implementação"},
    {"type": MessageType.CODE_GEN, "content": "Escrevendo código"},
    {"type": MessageType.TEST_GEN, "content": "Executando testes"},
    {"type": MessageType.TASK_END, "content": "Conversa finalizada com sucesso"},
]

for i, msg in enumerate(messages):
    source = agents[i % len(agents)]
    target = agents[(i + 1) % len(agents)]
    
    print(f"[{i+1}] {source} → {target}: {msg['content']}")
    bus.publish(
        message_type=msg["type"],
        source=source,
        target=target,
        content=msg["content"],
        metadata={"conversation_id": conversation_id, "iteration": i}
    )
    time.sleep(0.5)

print()
print("✅ Conversa simulada enviada para o bus")
print()
print("Aguardando processamento...")
time.sleep(2)

# Verificar se foi capturada
import requests
print()
print("🔍 Verificando se o interceptador capturou a conversa...")
print()

response = requests.get("http://localhost:8503/interceptor/conversations/active")
data = response.json()

if data.get("count", 0) > 0:
    print(f"✅ {data['count']} conversa(s) capturada(s)")
    print()
    for conv in data.get("conversations", []):
        print(f"  - ID: {conv.get('conversation_id')}")
        print(f"    Status: {conv.get('status')}")
        print(f"    Fase: {conv.get('current_phase')}")
        print(f"    Mensagens: {conv.get('message_count')}")
else:
    print("⚠️  Nenhuma conversa capturada")
    
    # Tentar histórico
    response = requests.get("http://localhost:8503/interceptor/conversations/history")
    hist = response.json()
    if isinstance(hist, dict) and hist.get("conversations"):
        print(f"\n✓ Mas encontradas no histórico:")
        for conv in hist.get("conversations", []):
            print(f"  - {conv}")
