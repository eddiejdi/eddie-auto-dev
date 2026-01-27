#!/usr/bin/env python3
"""Send questions to DirectorAgent and CoordinatorAgent via the local bus.

This script publishes request messages asking for authorization and
readiness checks for enabling autonomous actions and deploying Open WebUI.
"""

import uuid
import time
import importlib.util
import pathlib
import os

# Import agent_communication_bus directly from file to avoid package-level imports
bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType


def publish_requests():
    bus = get_communication_bus()
    req_id1 = str(uuid.uuid4())
    req_id2 = str(uuid.uuid4())

    director_msg = (
        "AUTONOMOUS_MODE was set to 1 in the repository. "
        "Do you authorize enabling autonomous remediation in production? "
        "If yes, list final safety checks and risks."
    )

    coordinator_msg = (
        "Requesting deployment of Open WebUI to production. "
        "Confirm tunnel API token availability, expected downtime, and any pre-deploy steps. "
        "If approved, respond with 'approve' and any extra commands."
    )

    # Use environment variable if present; otherwise default to local host mapping
    homelab_url = os.environ.get('HOMELAB_URL', 'http://192.168.15.2:3000')
    metadata1 = {'request_id': req_id1, 'url': homelab_url}
    metadata2 = {'request_id': req_id2, 'url': homelab_url}

    print(f"Publishing to DirectorAgent (request_id={req_id1})...")
    bus.publish(MessageType.REQUEST, 'assistant', 'DirectorAgent', director_msg, metadata1)
    # also publish to DB-IPC if available for cross-process delivery
    try:
        from tools import agent_ipc
        agent_ipc.publish_request('assistant', 'DirectorAgent', director_msg, metadata1)
    except Exception:
        pass

    time.sleep(0.2)

    print(f"Publishing to CoordinatorAgent (request_id={req_id2})...")
    bus.publish(MessageType.REQUEST, 'assistant', 'CoordinatorAgent', coordinator_msg, metadata2)
    try:
        from tools import agent_ipc
        agent_ipc.publish_request('assistant', 'CoordinatorAgent', coordinator_msg, metadata2)
    except Exception:
        pass

    print("Published both requests. Waiting briefly for in-process responses...")
    time.sleep(2)

    print("Done. If agents are running they should respond via the bus or DB IPC.")


if __name__ == '__main__':
    publish_requests()
