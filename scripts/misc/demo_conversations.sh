#!/bin/bash

# Demo: Simular Conversas e Testar Interface
# ============================================

cd ~/myClaude

echo "🎬 Demo: Simulando Conversas de Agentes"
echo "======================================="
echo ""

python3 << 'PYTHON_EOF'
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Setup path
sys.path.insert(0, str(Path.cwd()))

# Importar componentes
from specialized_agents.agent_interceptor import get_agent_interceptor
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

# Obter instâncias
interceptor = get_agent_interceptor()
bus = get_communication_bus()

# Gerar conversas de exemplo
print("📝 Simulando conversas dos agentes...\n")

# Simular mensagens
example_messages = [
    {
        "sender": "RequirementsAnalyst",
        "action": "analyze",
        "content": "Analisando requisitos do projeto: criar API REST em Python"
    },
    {
        "sender": "PythonAgent", 
        "action": "planning",
        "content": "Planejando arquitetura com FastAPI, SQLAlchemy e PostgreSQL"
    },
    {
        "sender": "PythonAgent",
        "action": "coding", 
        "content": "Implementando endpoints: GET /items, POST /items, DELETE /items/{id}"
    },
    {
        "sender": "TestAgent",
        "action": "testing",
        "content": "Executando suite de testes unitários... 45/45 testes passaram ✅"
    },
    {
        "sender": "OperationsAgent", 
        "action": "deployed",
        "content": "API deployada em produção. Health check: OK"
    }
]

# Simular mensagens
print("Enviando mensagens ao bus...")
for i, msg in enumerate(example_messages):
    bus.publish(
        message_type=MessageType.TASK_START,
        source=msg["sender"],
        target="all",
        content=f"[{msg['action']}] {msg['content']}",
        metadata={
            "phase": "coding",
            "action": msg["action"]
        }
    )
    print(f"  ✓ {msg['sender']}: {msg['action']}")

print("\n" + "="*70)
print("✅ Conversas simuladas com sucesso!")
print("="*70 + "\n")

# Mostrar estatísticas
stats = interceptor.get_stats()
print("📊 Estatísticas:")
print(f"  • Total de conversas: {stats['total_conversations']}")
print(f"  • Total de mensagens: {stats['total_messages_intercepted']}")
print(f"  • Conversas ativas: {stats['active_conversations']}")

# Listar conversas
conversations = interceptor.list_conversations(limit=5)
if conversations:
    print(f"\n📦 Conversas capturadas: {len(conversations)}")
    for conv in conversations[:1]:
        conv_id = conv.get('id', 'unknown')
        msg_count = conv.get('message_count', 0)
        print(f"  • {conv_id}: {msg_count} mensagens")

print("\n" + "="*70)
print("🚀 Agora execute para ver a interface:")
print("   bash start_simple_viewer.sh")
print("="*70)

PYTHON_EOF
