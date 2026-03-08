#!/usr/bin/env python3
"""
Validador de imports do sistema
"""
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent))

print("=== VALIDACAO DE IMPORTS ===\n")
errors = []

# 1. dev_agent.agent
try:
    from dev_agent.agent import DevAgent, ProjectSpec, Task, TaskStatus
    print("OK: dev_agent.agent")
except Exception as e:
    errors.append(f"dev_agent.agent: {e}")
    print(f"FAIL: dev_agent.agent - {e}")

# 2. dev_agent direto
try:
    from dev_agent import DevAgent, ProjectSpec
    print("OK: dev_agent direto")
except Exception as e:
    errors.append(f"dev_agent: {e}")
    print(f"FAIL: dev_agent - {e}")

# 3. specialized_agents
try:
    from specialized_agents import AgentManager, get_agent_manager
    print("OK: specialized_agents")
except Exception as e:
    errors.append(f"specialized_agents: {e}")
    print(f"FAIL: specialized_agents - {e}")

# 4. communication bus
try:
    from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
    print("OK: agent_communication_bus")
except Exception as e:
    errors.append(f"agent_communication_bus: {e}")
    print(f"FAIL: agent_communication_bus - {e}")

print(f"\n=== RESULTADO ===\nErros: {len(errors)}")
if errors:
    for e in errors:
        print(f"  - {e}")
    exit(1)
else:
    print("Todos os imports OK!")
    exit(0)
