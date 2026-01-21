#!/usr/bin/env python3
"""Invoke the Diretor model/agent via the communication bus.

This helper publishes a request targeted at the `DIRETOR` target so existing
listeners (or the Open WebUI 'Diretor Eddie' model) can pick it up.

Usage:
  ./tools/invoke_director.py "Please produce a safety checklist for enabling autonomous mode"
"""
import sys
import pathlib
import importlib.util

if len(sys.argv) < 2:
    print("Usage: invoke_director.py \"message\"")
    sys.exit(1)

message = sys.argv[1]

# Load bus by path to avoid package import overhead
bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

bus = get_communication_bus()
msg = bus.publish(MessageType.REQUEST, 'assistant', 'DIRETOR', message, {})
print('Bus publish:', msg.id if msg else 'failed')

# If Postgres IPC is available, also publish request there so cross-process listeners can pick it up
try:
    from tools import agent_ipc
    rid = agent_ipc.publish_request('assistant', 'DIRETOR', message, {'via': 'invoke_director'})
    print('DB publish id:', rid)
except Exception:
    pass
