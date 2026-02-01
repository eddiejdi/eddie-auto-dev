#!/usr/bin/env python3
"""Simple Diretor service: listens for REQUEST -> target 'DIRETOR' and replies.

The service replies with a brief authorization checklist. It also polls the
agent_ipc Postgres table (if available) for pending requests targeted to 'DIRETOR'.
"""

import time
import pathlib
import importlib.util
import traceback

# load bus module by path
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

try:
    from tools import agent_ipc
except Exception:
    agent_ipc = None


CHECKLIST = (
    "Diretor authorization:\n"
    "1) Confirm backup of DB and Open WebUI assets.\n"
    "2) Confirm tunnel API token present and valid.\n"
    "3) Confirm maintenance window and expected downtime.\n"
    "4) Confirm rollback image/tag available.\n"
    "5) Confirm monitoring/alerting configured post-deploy.\n"
    "If all OK, respond with 'approve' and list any additional steps."
)


def handle_bus(msg):
    try:
        if msg.message_type != MessageType.REQUEST:
            return
        if msg.target != "DIRETOR":
            return
        print(
            f"[Diretor] Received bus request from {msg.source}: {str(msg.content)[:200]}"
        )
        response = CHECKLIST
        bus = get_communication_bus()
        bus.publish(
            MessageType.RESPONSE,
            "DIRETOR",
            msg.source,
            response,
            {"request_id": msg.metadata.get("request_id") if msg.metadata else None},
        )
        # If DB ipc request id present, mark responded
        try:
            rid = msg.metadata.get("request_id") if msg.metadata else None
            if rid and agent_ipc:
                agent_ipc.respond(rid, "DIRETOR", response)
        except Exception:
            pass
    except Exception:
        print("[Diretor] handler error:\n", traceback.format_exc())


def db_loop(poll=5):
    if not agent_ipc:
        return
    print("[Diretor] DB polling enabled")
    while True:
        try:
            rows = agent_ipc.fetch_pending("DIRETOR", limit=5)
            for r in rows:
                rid = r["id"]
                src = r.get("source")
                content = r.get("content")
                print(
                    f"[Diretor] Processing DB request {rid} from {src}: {str(content)[:200]}"
                )
                agent_ipc.respond(rid, "DIRETOR", CHECKLIST)
        except Exception:
            pass
        time.sleep(poll)


def main():
    bus = get_communication_bus()
    bus.subscribe(handle_bus)
    if agent_ipc:
        # start DB loop in background
        import threading

        t = threading.Thread(target=db_loop, daemon=True)
        t.start()
    print("[Diretor] Listening on bus for requests...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Diretor] Shutting down")


if __name__ == "__main__":
    main()
