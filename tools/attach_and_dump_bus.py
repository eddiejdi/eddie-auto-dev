#!/usr/bin/env python3
"""Attach to the Agent Communication Bus, print recent messages and listen for new ones.
Usage: python3 tools/attach_and_dump_bus.py [seconds]
"""
import sys
import time
import json
import pathlib
import importlib.util

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 20

bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

bus = get_communication_bus()

print('=== Bus stats ===')
print(json.dumps(bus.get_stats(), default=str, indent=2, ensure_ascii=False))

print('\n=== Last 50 messages ===')
msgs = bus.get_messages(limit=50)
for m in msgs:
    print('---')
    print(json.dumps(m.to_dict(), ensure_ascii=False, indent=2))

print(f"\nListening for new messages for {secs} seconds...\n")

def cb(m):
    try:
        print('New message:')
        print(json.dumps(m.to_dict(), ensure_ascii=False, indent=2))
    except Exception as e:
        print('Callback error', e)

bus.subscribe(cb)
try:
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    bus.unsubscribe(cb)
    print('\nDone listening.')
