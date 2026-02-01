#!/usr/bin/env python3
"""Testar funções do viewer"""

import sys

sys.path.insert(0, "/home/eddie/myClaude")

from specialized_agents.simple_conversation_viewer import fetch_conversations, get_stats

print("=== Stats ===")
stats = get_stats()
print(stats)

print("\n=== Conversations ===")
text = fetch_conversations()
print(text[:2000] if len(text) > 2000 else text)
