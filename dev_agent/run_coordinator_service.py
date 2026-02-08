#!/usr/bin/env python3
"""Run CoordinatorAgent as a long-running service that listens on the AgentCommunicationBus.

This service subscribes to REQUEST messages targeted to 'CoordinatorAgent' or 'agent_coordinator',
executes `CoordinatorAgent.decide_and_execute` for the request content, and publishes a RESPONSE.
"""
import asyncio
import time
import json
import traceback
from dev_agent.coordinator import create_coordinator

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType


def handle_message(msg):
    try:
        if msg.message_type != MessageType.REQUEST:
            return
        if msg.target not in ('CoordinatorAgent', 'agent_coordinator'):
            return

        content = msg.content or ''
        print(f"[CoordinatorService] Received request from {msg.source}: {content[:200]}")

        # Run coordinator decide_and_execute synchronously via asyncio
        coord = create_coordinator()
        try:
            res = asyncio.run(coord.decide_and_execute(content))
            out = json.dumps(res, ensure_ascii=False)
        except Exception as e:
            out = json.dumps({'error': str(e), 'trace': traceback.format_exc()})

        bus = get_communication_bus()
        bus.publish(MessageType.RESPONSE, 'CoordinatorAgent', msg.source, out, {'request_id': msg.metadata.get('request_id') if msg.metadata else None})
    except Exception:
        print("[CoordinatorService] handler error:\n", traceback.format_exc())


def main():
    bus = get_communication_bus()
    bus.subscribe(handle_message)
    print("[CoordinatorService] Listening for requests on the AgentCommunicationBus...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[CoordinatorService] Shutting down")


if __name__ == '__main__':
    main()
