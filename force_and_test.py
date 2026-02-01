#!/usr/bin/env python3
"""Script para forçar interações e persistir no banco de dados"""

import sys
import os

sys.path.insert(0, "/home/eddie/myClaude")
os.chdir("/home/eddie/myClaude")

# Forçar criação do interceptor que vai persistir no SQLite
from specialized_agents.agent_interceptor import get_agent_interceptor
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)

# Obter instâncias (singletons dentro deste processo)
interceptor = get_agent_interceptor()
bus = get_communication_bus()

print("🚀 Forçando interações entre agentes com persistência...")
print("=" * 60)

# Mensagens para enviar
msgs = [
    (
        "PythonAgent",
        "RequirementsAnalyst",
        "Solicitando análise de requisitos para novo módulo de autenticação",
    ),
    (
        "RequirementsAnalyst",
        "PythonAgent",
        "Requisitos analisados: criar API REST com FastAPI e JWT",
    ),
    (
        "PythonAgent",
        "TestAgent",
        "Código implementado em auth_service.py, solicito testes",
    ),
    ("TestAgent", "PythonAgent", "Executando 25 testes unitários... 24/25 passaram"),
    ("TestAgent", "OperationsAgent", "Testes OK após correção, pronto para deploy"),
    ("OperationsAgent", "all", "Iniciando deploy em produção - v2.1.0"),
    ("JavaScriptAgent", "PythonAgent", "Preciso integrar frontend React com sua API"),
    (
        "PythonAgent",
        "JavaScriptAgent",
        "Endpoint disponível em /api/v1/auth - docs em /docs",
    ),
    ("TypeScriptAgent", "TestAgent", "Solicito revisão de tipos TypeScript"),
    ("GoAgent", "OperationsAgent", "Microservice de cache pronto para deploy"),
]

for src, tgt, content in msgs:
    # Publicar no bus (que notifica o interceptor automaticamente)
    bus.publish(MessageType.REQUEST, src, tgt, content)
    print(f"✓ {src} → {tgt}")
    print(f"  {content[:60]}...")

print("=" * 60)
print(f"✅ {len(msgs)} mensagens enviadas!")

# Verificar se foram persistidas
import sqlite3
from pathlib import Path
from specialized_agents.config import DATA_DIR

db_path = Path(DATA_DIR) / "interceptor_data" / "conversations.db"
print(f"\n📁 Verificando banco: {db_path}")

if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages")
    count = cursor.fetchone()[0]
    print(f"📊 Total de mensagens no banco: {count}")

    cursor.execute("SELECT DISTINCT conversation_id FROM messages")
    convs = cursor.fetchall()
    print(f"📂 Conversas únicas: {len(convs)}")

    cursor.execute(
        "SELECT conversation_id, source, target, content FROM messages ORDER BY timestamp DESC LIMIT 5"
    )
    rows = cursor.fetchall()
    print("\n📝 Últimas 5 mensagens:")
    for row in rows:
        print(f"  [{row[0][:20]}...] {row[1]} → {row[2]}: {row[3][:50]}...")

    conn.close()
else:
    print("❌ Banco não encontrado!")

print("\n🔄 Testando list_conversations...")
convs = interceptor.list_conversations(limit=10)
print(f"📊 Conversas retornadas: {len(convs)}")
for conv in convs[:3]:
    print(
        f"  - ID: {conv.get('id', 'N/A')[:30]}... | Mensagens: {conv.get('message_count', 0)}"
    )
