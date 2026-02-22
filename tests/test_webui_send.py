import asyncio
import pytest

from specialized_agents.api import webui_send, CommunicationRequest
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType


@pytest.mark.asyncio
async def test_webui_send_filters_only_webui():
    bus = get_communication_bus()
    # start from a clean slate
    bus.clear()

    async def publisher():
        # wait a bit so subscription is active
        await asyncio.sleep(0.05)
        # send a broadcast and a message targeted specifically at webui
        bus.publish(MessageType.RESPONSE, "agentA", "all", "broadcast")
        bus.publish(MessageType.RESPONSE, "agentB", "webui", "private")
        # also send to other recipient which shouldn't be captured
        bus.publish(MessageType.RESPONSE, "agentC", "other", "ignored")

    # schedule the publisher task
    asyncio.create_task(publisher())

    # call webui_send with a short timeout
    # timeout must be int according to Pydantic model
    req = CommunicationRequest(content="hello", wait_for_responses=True, timeout=1)
    result = await webui_send(req)

    assert result["responses_count"] == 1
    assert len(result["responses"]) == 1
    resp = result["responses"][0]
    assert resp["target"] == "webui"
    assert resp["content"] == "private"


def test_webui_send_with_responder_echo(monkeypatch):
    # ensure the in-process responder is active
    from specialized_agents.agent_responder import start_responder
    start_responder()

    # patch get_agent_manager so responder thinks there's no active agents and
    # falls back to echo logic only (the echo handles webui source specially)
    # actually the early return logic doesn't consult manager, so no need to patch

    # clear bus before we start
    from specialized_agents.agent_communication_bus import get_communication_bus
    bus = get_communication_bus()
    bus.clear()

    # send using webui_send and expect the same text echoed back
    req = CommunicationRequest(content="echo test", wait_for_responses=True, timeout=1)
    result = __import__('asyncio').run(webui_send(req))
    assert result["responses_count"] == 1
    echo = result["responses"][0]
    assert echo["content"] == "echo test"
    assert echo["source"].startswith("assistant"), "response source should be the assistant"
    assert echo["target"].startswith("webui")
