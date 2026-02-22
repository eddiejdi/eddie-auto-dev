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

@pytest.mark.asyncio
async def test_webui_send_director_included(monkeypatch):
    """Guarantee that responses from the director are returned by webui_send."""
    bus = get_communication_bus()
    bus.clear()

    # when webui_send publishes a clarification to DIRETOR we simulate a
    # director response a short time later
    async def fake_dir():
        await asyncio.sleep(0.05)
        # publish a reply addressed to the webui source
        bus.publish(MessageType.RESPONSE, "DIRETOR", "webui", "resp from director")

    # schedule on current loop
    asyncio.get_running_loop().create_task(fake_dir())

    req = CommunicationRequest(
        content="ask director",
        wait_for_responses=True,
        timeout=1,
        clarify_to_director=True,
    )
    result = await webui_send(req)

    # should have at least one response sourced from DIRETOR
    assert any(r["source"] == "DIRETOR" for r in result["responses"]), "Director reply not captured"

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
    # deve haver pelo menos uma resposta gerada (pode ser eco se LLM falhar)
    assert result["responses_count"] >= 1
    resp = result["responses"][0]
    assert resp["source"].startswith("assistant")
    assert resp["target"].startswith("webui")
    # conteúdo não pode ficar vazio
    assert resp["content"].strip() != ""
