"""
Agent responder for coordinator test broadcasts.
Listens for coordinator messages on the communication bus and
emits a `response` message per active agent so tests can validate flow.
This is intentionally lightweight and only used for testing/validation.
"""
import json
import threading
import time
from typing import Any

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType, log_response
from specialized_agents import get_agent_manager


def _handle_message(message: Any):
    try:
        if message.message_type != MessageType.COORDINATOR:
            return

        # try to parse content as JSON to detect op
        op = None
        try:
            payload = json.loads(message.content)
            op = payload.get("op")
        except Exception:
            # content may be plain text
            if "please_respond" in message.content or "por favor respondam" in message.content:
                op = "please_respond"

        if op != "please_respond":
            return

        # Spawn a thread to avoid blocking bus callbacks
        def respond():
            mgr = get_agent_manager()
            # give a small pause so active agents may initialize
            time.sleep(0.2)
            active = mgr.list_active_agents()
            for a in active:
                try:
                    agent_name = a.get("name") or a.get("language")
                    content = f"{agent_name} resposta automática ao broadcast: {message.content[:200]}"
                    log_response(agent_name, "coordinator", content)
                except Exception:
                    pass

        t = threading.Thread(target=respond, daemon=True)
        t.start()
    except Exception:
        pass


def start_responder():
    bus = get_communication_bus()
    bus.subscribe(_handle_message)


__all__ = ["start_responder"]
