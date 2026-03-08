#!/usr/bin/env python3
"""
Forçar interações entre agentes E verificar captura
Tudo no mesmo processo para garantir que o interceptor capture
"""
import sys
import time
sys.path.insert(0, '/home/shared/myClaude')

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
from specialized_agents.agent_interceptor import get_agent_interceptor

# Primeiro, obter o interceptor (isso registra no bus automaticamente)
print("🔧 Inicializando interceptor...")
interceptor = get_agent_interceptor()

# Verificar stats iniciais
stats_before = interceptor.get_stats()
print(f"📊 Stats ANTES: {stats_before['total_messages_intercepted']} mensagens")

# Agora obter o bus (mesmo singleton)
bus = get_communication_bus()

# Forçar interações entre agentes
msgs = [
    (MessageType.REQUEST, 'PythonAgent', 'RequirementsAnalyst', 'Solicitando análise de requisitos para novo módulo'),
    (MessageType.RESPONSE, 'RequirementsAnalyst', 'PythonAgent', 'Requisitos: API REST com FastAPI e JWT auth'),
    (MessageType.TASK_START, 'PythonAgent', 'system', 'Iniciando implementação do auth_service.py'),
    (MessageType.CODE_GEN, 'PythonAgent', 'system', 'Código gerado: 150 linhas de Python'),
    (MessageType.REQUEST, 'PythonAgent', 'TestAgent', 'Código pronto, solicito testes unitários'),
    (MessageType.TASK_START, 'TestAgent', 'system', 'Executando pytest...'),
    (MessageType.RESPONSE, 'TestAgent', 'PythonAgent', '25/25 testes passaram ✅'),
    (MessageType.REQUEST, 'TestAgent', 'OperationsAgent', 'Pronto para deploy'),
    (MessageType.TASK_START, 'OperationsAgent', 'system', 'Iniciando deploy v2.1.0'),
    (MessageType.RESPONSE, 'OperationsAgent', 'all', 'Deploy concluído com sucesso! 🚀'),
]

print("\n🚀 Enviando mensagens ao bus...")
print("=" * 60)

for msg_type, src, tgt, content in msgs:
    bus.publish(msg_type, src, tgt, content)
    print(f"✓ [{msg_type.value}] {src} → {tgt}")
    time.sleep(0.1)  # Pequeno delay para garantir processamento

print("=" * 60)

# Verificar stats depois
time.sleep(0.5)
stats_after = interceptor.get_stats()
print(f"\n📊 Stats DEPOIS: {stats_after['total_messages_intercepted']} mensagens")

# Listar conversas
convs = interceptor.list_conversations(limit=20)
print(f"📦 Conversas capturadas: {len(convs)}")

for c in convs:
    cid = c.get('id', c.get('conversation_id', 'N/A'))
    status = c.get('status', 'N/A')
    msg_count = c.get('message_count', 0)
    print(f"  - {cid}: {status} ({msg_count} msgs)")

print("\n✅ Concluído! Atualize a Tela Diretor (F5)")
