#!/usr/bin/env python3
"""Collect agent responses from the local AgentCommunicationBus for a short period.

Usage: run the script; it listens for 5 seconds and prints any RESPONSE messages.
"""
import time
import pathlib
import importlib.util
import json

# Load bus module by path to avoid importing the whole package
bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType


def main(timeout=5):
    bus = get_communication_bus()
    found = []

    def handler(msg):
        try:
            if msg.message_type == MessageType.RESPONSE:
                found.append(msg)
        except Exception:
            pass

    bus.subscribe(handler)
    print(f"Listening for RESPONSE messages on the bus for {timeout} seconds...")
    time.sleep(timeout)
    bus.unsubscribe(handler)

    if not found:
        print("No RESPONSE messages observed in the period.")
        return

    print(f"Collected {len(found)} RESPONSE messages:")
    for m in found:
        out = {
            'id': m.id,
            'timestamp': m.timestamp.isoformat(),
            'source': m.source,
            'target': m.target,
            'content': m.content,
            'metadata': m.metadata,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main(5)
