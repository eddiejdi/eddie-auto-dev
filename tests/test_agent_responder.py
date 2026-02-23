import time
import pytest

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
from specialized_agents.agent_responder import start_responder
import specialized_agents


class DummyManagerActive:
    def list_active_agents(self):
        return [{"name": "FakeAgent", "language": "fake"}]


class DummyManagerEmpty:
    def list_active_agents(self):
        return []


def setup_function(fn):
    # Ensure a clean bus for each test
    bus = get_communication_bus()
    bus.clear()
    # Clear subscribers so successive test runs don't double-subscribe handlers
    try:
        bus.subscribers.clear()
    except Exception:
        pass


def test_agent_responder_with_active_agent(monkeypatch):
    bus = get_communication_bus()

    # Patch the responder's get_agent_manager reference (it imports this symbol at module import time)
    monkeypatch.setattr("specialized_agents.agent_responder.get_agent_manager", lambda: DummyManagerActive())

    start_responder()

    bus.publish(MessageType.COORDINATOR, "coordinator", "all", "please_respond")

    # Wait briefly for responder thread to run
    time.sleep(0.4)

    responses = bus.get_messages(limit=50, message_types=[MessageType.RESPONSE])
    assert any("FakeAgent" in m.content for m in responses), "Expected a response from FakeAgent"


def test_agent_responder_fallback(monkeypatch):
    bus = get_communication_bus()

    # Patch the responder's get_agent_manager to return no active agents
    monkeypatch.setattr("specialized_agents.agent_responder.get_agent_manager", lambda: DummyManagerEmpty())

    start_responder()

    bus.publish(MessageType.COORDINATOR, "coordinator", "all", "please_respond")

    time.sleep(0.4)

    responses = bus.get_messages(limit=50, message_types=[MessageType.RESPONSE])
    assert any("Nenhum agente ativo" in m.content for m in responses), "Expected fallback message when no agents active"


def test_agent_responder_echoes_webui():
    bus = get_communication_bus()

    # start responder normally
    start_responder()

    # send a message that mimics WebUI (source automatically set by bus)
    bus.publish(MessageType.REQUEST, "webui:tester", "all", "hello from webui")

    # allow responder to react
    time.sleep(0.2)

    responses = bus.get_messages(limit=50, message_types=[MessageType.RESPONSE])
    # should contain a response targeted back to the webui source
    assert any(m.target == "webui:tester" and "hello from webui" in m.content for m in responses), \
        "Responder should echo content back to webui source"
