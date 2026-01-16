#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/eddie/myClaude')
from specialized_agents.agent_interceptor import get_agent_interceptor

i = get_agent_interceptor()
convs = i.list_conversations(limit=20)
print(f"Total de conversas: {len(convs)}")
for c in convs:
    print(f"  - ID: {c.get('id', 'N/A')}, Status: {c.get('status', 'N/A')}, Msgs: {c.get('message_count', 0)}")

stats = i.get_stats()
print(f"\nEstatísticas:")
print(f"  Total conversas: {stats.get('total_conversations', 0)}")
print(f"  Mensagens interceptadas: {stats.get('total_messages_intercepted', 0)}")
print(f"  Conversas ativas: {stats.get('active_conversations', 0)}")
