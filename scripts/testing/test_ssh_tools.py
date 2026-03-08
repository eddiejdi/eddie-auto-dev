#!/usr/bin/env python3
"""Teste das ferramentas SSH MCP"""
import sys
sys.path.insert(0, '/home/homelab/myClaude')

from ssh_agent_mcp import MCPServer

server = MCPServer()
tools = server.get_tools_schema()

print(f'Total de ferramentas: {len(tools)}')
print()
for t in tools:
    desc = t["description"][:100] + "..." if len(t["description"]) > 100 else t["description"]
    print(f'✓ {t["name"]}')
    print(f'  {desc}')
    print()
