#!/usr/bin/env python3
import time
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)


def main():
    print("Monitorando mensagens do bus (REQUEST/RESPONSE para DIRETOR)...")
    bus = get_communication_bus()
    seen = set()
    start = time.time()
    while time.time() - start < 180:
        msgs = bus.get_messages(limit=30)
        for m in msgs:
            if m.id in seen:
                continue
            if m.message_type in [MessageType.REQUEST, MessageType.RESPONSE] and (
                "DIRETOR" in m.target or m.source == "DIRETOR"
            ):
                print(
                    f"[{m.timestamp}] {m.message_type.value} {m.source} → {m.target}: {m.content} (meta={m.metadata})"
                )
                seen.add(m.id)
        time.sleep(5)
    print("Monitoramento encerrado.")


if __name__ == "__main__":
    main()
