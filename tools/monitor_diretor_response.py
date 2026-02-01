#!/usr/bin/env python3
import time

# Import robusto do bus: tenta import normal e faz fallback por caminho absoluto se necessário
try:
    from specialized_agents.agent_communication_bus import (
        get_communication_bus,
        MessageType,
    )
except Exception:
    import pathlib
    import importlib.util

    bus_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "specialized_agents"
        / "agent_communication_bus.py"
    )
    spec = importlib.util.spec_from_file_location("agent_bus_local", str(bus_path))
    agent_bus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_bus)
    get_communication_bus = agent_bus.get_communication_bus
    MessageType = agent_bus.MessageType


def main():
    print("Aguardando resposta do DIRETOR no bus...")
    bus = get_communication_bus()
    start = time.time()
    last_seen = set()
    while time.time() - start < 120:
        msgs = bus.get_messages(
            limit=20, message_types=[MessageType.RESPONSE], source="DIRETOR"
        )
        new_msgs = [m for m in msgs if m.id not in last_seen]
        for m in new_msgs:
            print(f"[{m.timestamp}] {m.content}\n(meta={m.metadata})")
            last_seen.add(m.id)
        if new_msgs:
            print("---")
        time.sleep(5)
    print("Monitoramento encerrado.")


if __name__ == "__main__":
    main()
