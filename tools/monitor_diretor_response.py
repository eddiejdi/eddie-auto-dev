#!/usr/bin/env python3
import time
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

def main():
    print('Aguardando resposta do DIRETOR no bus...')
    bus = get_communication_bus()
    start = time.time()
    last_seen = set()
    while time.time() - start < 120:
        msgs = bus.get_messages(limit=20, message_types=[MessageType.RESPONSE], source='DIRETOR')
        new_msgs = [m for m in msgs if m.id not in last_seen]
        for m in new_msgs:
            print(f'[{m.timestamp}] {m.content}\n(meta={m.metadata})')
            last_seen.add(m.id)
        if new_msgs:
            print('---')
        time.sleep(5)
    print('Monitoramento encerrado.')

if __name__ == '__main__':
    main()
