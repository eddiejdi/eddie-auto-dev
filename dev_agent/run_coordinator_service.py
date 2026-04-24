"""Run CoordinatorAgent as a long-running service that listens on the AgentCommunicationBus.

This service subscribes to REQUEST messages targeted to 'CoordinatorAgent' or 'agent_coordinator',
executes `CoordinatorAgent.decide_and_execute` for the request content, and publishes a RESPONSE.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
import traceback

logger = logging.getLogger("dev_agent.coordinator_service")


def _build_coordinator():
    from dev_agent.config import OLLAMA_HOST, OLLAMA_MODEL
    from dev_agent.llm_client import LLMClient
    from dev_agent.agent import DevAgent
    from dev_agent.coordinator import CoordinatorAgent

    llm = LLMClient(base_url=OLLAMA_HOST, model=OLLAMA_MODEL)
    agent = DevAgent(llm_url=OLLAMA_HOST, model=OLLAMA_MODEL)
    rag_url = os.getenv("RAG_API_URL", "")
    coordinator = CoordinatorAgent(dev_agent=agent, rag_api_url=rag_url)
    return coordinator


def handle_message(msg) -> None:
    from specialized_agents.agent_communication_bus import (
        AgentCommunicationBus,
        MessageType,
    )

    bus = AgentCommunicationBus()
    if msg.message_type.value != "request":
        return
    if msg.target not in ("CoordinatorAgent", "agent_coordinator"):
        return

    logger.info("[CoordinatorService] Received request from %s", msg.source)
    request_id = msg.metadata.get("request_id", msg.id)

    try:
        coordinator = _build_coordinator()
        result = coordinator.decide_and_execute(msg.content)
        response_content = str(result)
    except Exception:
        response_content = "[CoordinatorService] handler error:\n" + traceback.format_exc()
        logger.error(response_content)

    bus.publish(
        message_type=MessageType.RESPONSE,
        source="CoordinatorAgent",
        target=msg.source,
        content=response_content,
        metadata={"request_id": request_id},
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from specialized_agents.agent_communication_bus import AgentCommunicationBus

    bus = AgentCommunicationBus()
    bus.recording = True
    bus.subscribe(handle_message)

    logger.info("[CoordinatorService] Listening for requests on the AgentCommunicationBus...")

    stop = False

    def _handle_signal(sig, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        while not stop:
            time.sleep(1)
    finally:
        bus.unsubscribe(handle_message)
        logger.info("[CoordinatorService] Shutting down")


if __name__ == "__main__":
    main()
