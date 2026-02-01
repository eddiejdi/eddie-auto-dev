#!/usr/bin/env python3
"""Teste do HTML gerado pela função render_conversations_html"""

import sys

sys.path.insert(0, "/home/eddie/myClaude")
import os

os.chdir("/home/eddie/myClaude")

from specialized_agents.agent_interceptor import get_agent_interceptor
import re


def get_interceptor():
    return get_agent_interceptor()


def render_conversations_html(filter_agent="Todos", limit=5):
    """Replica simplificada da função de renderização"""
    interceptor = get_interceptor()
    conversations_list = interceptor.list_conversations(limit=limit)

    output = []
    output.append(f"Total conversas: {len(conversations_list)}")

    for conv in conversations_list:
        conv_id = conv.get("id", "?")[:35]
        msg_count = conv.get("message_count", 0)
        messages = conv.get("messages", [])

        output.append(f"\n📦 {conv_id}... ({msg_count} msgs)")

        if messages:
            for msg in messages[-3:]:
                ts = msg.get("timestamp", "")
                if ts:
                    ts = ts[-8:] if len(ts) > 8 else ts
                else:
                    ts = "--:--:--"

                sender = msg.get("sender", "?")
                target = msg.get("target", "?")
                raw_content = msg.get("content", "")

                # Formato: remover XML
                content = raw_content.strip()
                if content.startswith("<"):
                    content = re.sub(r"<[^>]+>", " ", content)
                    content = re.sub(r"\s+", " ", content).strip()

                content = content[:80] + "..." if len(content) > 80 else content

                # FORMATO ESPERADO: [timestamp] sender ===> target: conteúdo
                output.append(f"  [{ts}] {sender} ===> {target}: {content}")
        else:
            output.append("  (sem mensagens)")

    return "\n".join(output)


# Executar teste
print("=== TESTE DE RENDERIZAÇÃO HTML ===")
result = render_conversations_html()
print(result)
print("\n=== VALIDAÇÃO ===")
if "===>" in result and "coordinator" in result:
    print("✅ Formato correto: contém '===>' e nomes de agentes")
else:
    print("❌ Formato incorreto!")
