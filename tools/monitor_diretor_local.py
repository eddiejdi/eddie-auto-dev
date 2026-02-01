#!/usr/bin/env python3
"""Monitor simples do DIRETOR via AgentCommunicationBus (execução local).

Uso: python3 tools/monitor_diretor_local.py [timeout_seconds]
"""

import sys
import time
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta


def load_bus():
    bus_path = (
        Path(__file__).resolve().parents[1]
        / "specialized_agents"
        / "agent_communication_bus.py"
    )
    spec = importlib.util.spec_from_file_location("agent_bus_local", str(bus_path))
    agent_bus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_bus)
    return (
        agent_bus.get_communication_bus(),
        agent_bus.MessageType,
        agent_bus.log_response,
        agent_bus.log_error,
    )


def main(timeout: int = 60):
    bus, MessageType, log_response, log_error = load_bus()
    start = datetime.now()
    deadline = start + timedelta(seconds=timeout)
    seen = set()
    print(
        f"Monitor started, listening for DIRETOR responses until {deadline.isoformat()}"
    )
    while datetime.now() < deadline:
        msgs = bus.get_messages(
            limit=200,
            message_types=[MessageType.RESPONSE, MessageType.ERROR],
            source="DIRETOR",
        )
        new = [m for m in msgs if m.id not in seen]
        for m in new:
            seen.add(m.id)
            ts = m.timestamp.isoformat()
            print(
                f"[{ts}] {m.message_type.value.upper()} from {m.source} -> {m.target}: {m.content}"
            )
            try:
                with open(f"/tmp/diretor_msg_{m.id}.txt", "w") as f:
                    f.write(
                        f"{ts} {m.message_type.value} {m.source} {m.target}\n{m.content}\n\nMETADATA:\n{m.metadata}\n"
                    )
            except Exception:
                pass
        time.sleep(1)
    print("Monitor finished (timeout)")


if __name__ == "__main__":
    t = 60
    if len(sys.argv) > 1:
        try:
            t = int(sys.argv[1])
        except Exception:
            pass
    main(t)
