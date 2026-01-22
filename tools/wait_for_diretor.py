#!/usr/bin/env python3
"""Wait for DIRETOR response on the communication bus and save it to /tmp/diretor_response.json

Usage: python3 tools/wait_for_diretor.py
"""
import json
import pathlib
import importlib.util
import sys
import time

bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

OUTFILE = '/tmp/diretor_response.json'

def handle(msg):
    try:
        if msg.message_type != MessageType.RESPONSE:
            return
        if msg.source != 'DIRETOR' and 'DIRETOR' not in msg.source:
            return
        print('[wait_for_diretor] Received response from DIRETOR:')
        print(msg.content)
        payload = {
            'id': msg.id,
            'timestamp': msg.timestamp.isoformat(),
            'source': msg.source,
            'target': msg.target,
            'content': msg.content,
            'metadata': msg.metadata,
        }
        with open(OUTFILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f'[wait_for_diretor] Wrote response to {OUTFILE} and exiting')
        sys.exit(0)
    except Exception as e:
        print('Handler error', e)


def main(timeout=600):
    bus = get_communication_bus()
    bus.subscribe(handle)
    print('[wait_for_diretor] Listening for DIRETOR response (timeout', timeout, 's)')
    start = time.time()
    try:
        while True:
            time.sleep(0.5)
            if time.time() - start > timeout:
                print('[wait_for_diretor] Timeout reached, exiting')
                break
    except KeyboardInterrupt:
        print('[wait_for_diretor] Interrupted')


if __name__ == '__main__':
    main()
