#!/usr/bin/env python3
"""Script de testes de validação da aplicação"""

import sys

sys.path.insert(0, "/home/eddie/myClaude")

from specialized_agents.agent_interceptor import get_agent_interceptor
from specialized_agents.simple_conversation_viewer import (
    render_conversations_html,
    get_stats,
)

print("=" * 50)
print("EXECUTANDO TESTES DE VALIDACAO")
print("=" * 50)

# Test 1: Interceptor initialization
interceptor = get_agent_interceptor()
print("Test 1 - Interceptor: OK")

# Test 2: List conversations
convs = interceptor.list_conversations(limit=10)
assert len(convs) > 0, "No conversations found"
print(f"Test 2 - List Conversations: OK ({len(convs)} found)")

# Test 3: Get stats
stats = get_stats()
assert "error" not in stats, f"Stats error: {stats}"
print(f"Test 3 - Stats: OK (msgs={stats.get('total_messages', 0)})")

# Test 4: Render HTML conversations
html = render_conversations_html()
assert (
    "stream-container" in html or "CONVERSA" in html or "empty-state" in html
), "Invalid HTML"
print("Test 4 - Render HTML: OK")

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
