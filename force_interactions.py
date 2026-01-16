#!/usr/bin/env python3
"""Forçar interações entre agentes"""
import sys
sys.path.insert(0, '/home/eddie/myClaude')

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()

# Forçar interações entre agentes
msgs = [
    ('PythonAgent', 'RequirementsAnalyst', 'Solicitando análise de requisitos para novo módulo de autenticação'),
    ('RequirementsAnalyst', 'PythonAgent', 'Requisitos analisados: criar API REST com FastAPI e JWT'),
    ('PythonAgent', 'TestAgent', 'Código implementado em auth_service.py, solicito testes'),
    ('TestAgent', 'PythonAgent', 'Executando 25 testes unitários... 24/25 passaram'),
    ('TestAgent', 'OperationsAgent', 'Testes OK após correção, pronto para deploy'),
    ('OperationsAgent', 'all', 'Iniciando deploy em produção - v2.1.0'),
    ('JavaScriptAgent', 'PythonAgent', 'Preciso integrar frontend React com sua API'),
    ('PythonAgent', 'JavaScriptAgent', 'Endpoint disponível em /api/v1/auth - docs em /docs'),
    ('TypeScriptAgent', 'TestAgent', 'Solicito revisão de tipos TypeScript'),
    ('GoAgent', 'OperationsAgent', 'Microservice de cache pronto para deploy'),
]

print("🚀 Forçando interações entre agentes...")
print("=" * 60)

for src, tgt, content in msgs:
    bus.publish(MessageType.REQUEST, src, tgt, content)
    print(f"✓ {src} → {tgt}")
    print(f"  {content[:60]}...")

print("=" * 60)
print(f"✅ {len(msgs)} mensagens enviadas ao bus!")
print("\n📺 Atualize a Tela Diretor para ver as conversas!")
