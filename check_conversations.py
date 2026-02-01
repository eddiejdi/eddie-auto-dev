#!/usr/bin/env python3
"""Script para testar exatamente o que a tela deveria mostrar"""

import sys

sys.path.insert(0, "/home/eddie/myClaude")
from specialized_agents.agent_interceptor import get_agent_interceptor

interceptor = get_agent_interceptor()
convs = interceptor.list_conversations(limit=5)
print("=== TESTE DE VISUALIZAÇÃO ===")
print(f"Total conversas: {len(convs)}")

for conv in convs[:3]:
    conv_id = conv.get("id", "?")[:35]
    msgs = conv.get("messages", [])
    msg_count = len(msgs)
    print(f"\nConv: {conv_id}... ({msg_count} msgs)")

    if msgs:
        for m in msgs[:3]:
            sender = m.get("sender", "?")
            target = m.get("target", "?")
            content = str(m.get("content", ""))[:80]
            # Formato esperado: NomeAgente ===> Destino: Mensagem
            print(f"  [{sender}] ===> [{target}]: {content}")
    else:
        print("  (sem mensagens)")

print("\n=== FIM DO TESTE ===")
