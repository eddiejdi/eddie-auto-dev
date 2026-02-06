#!/usr/bin/env python3
"""Script de teste para ssh_execute_on"""
import os
from ssh_agent_mcp import MCPServer
import json

server = MCPServer()

# Testar execute_on
print("Testando ssh_execute_on...")
HOST = os.environ.get('HOMELAB_HOST', '192.168.15.2')
result = server.tool_execute_on({
    "hostname": HOST,
    "username": "homelab",
    "password": "homelab",
    "command": "hostname && uptime"
})
print(json.dumps(result, indent=2))
