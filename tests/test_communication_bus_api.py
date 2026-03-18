"""Testes para as rotas /communication/* da API especializada."""
from __future__ import annotations

from fastapi.testclient import TestClient

from specialized_agents.api import app
from specialized_agents.agent_communication_bus import get_communication_bus

client = TestClient(app)


def setup_function():
    """Limpa o bus antes de cada teste."""
    get_communication_bus().clear()


def test_communication_messages_returns_empty_initially():
    """GET /communication/messages deve retornar lista vazia quando bus está vazio."""
    resp = client.get("/communication/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert "messages" in body
    assert body["total"] == 0


def test_communication_publish_and_retrieve():
    """POST /communication/publish deve adicionar mensagem recuperável via GET."""
    payload = {
        "source": "test-agent",
        "target": "homelab-advisor",
        "content": "mensagem de teste",
        "message_type": "request",
    }
    resp = client.post("/communication/publish", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert result["success"] is True
    assert "id" in result

    resp2 = client.get("/communication/messages")
    assert resp2.status_code == 200
    messages = resp2.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["source"] == "test-agent"
    assert messages[0]["target"] == "homelab-advisor"


def test_communication_send_alias():
    """/communication/send deve ser equivalente a /communication/publish."""
    payload = {"source": "sender", "target": "all", "content": "broadcast"}
    resp = client.post("/communication/send", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_communication_stats_returns_counts():
    """GET /communication/stats deve retornar estatísticas do bus."""
    client.post("/communication/publish", json={
        "source": "agent-x", "target": "all", "content": "test stats"
    })
    resp = client.get("/communication/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_messages" in stats
    assert stats["total_messages"] >= 1


def test_communication_clear():
    """POST /communication/clear deve esvaziar o buffer."""
    client.post("/communication/publish", json={
        "source": "a", "target": "b", "content": "msg to clear"
    })
    clear_resp = client.post("/communication/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["cleared"] is True

    resp = client.get("/communication/messages")
    assert resp.json()["total"] == 0


def test_communication_pause_resume():
    """Pause/resume controlam gravação no bus."""
    pause_resp = client.post("/communication/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["recording"] is False

    resume_resp = client.post("/communication/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["recording"] is True


def test_messages_filter_by_target():
    """GET /communication/messages?target=X deve filtrar por destino."""
    client.post("/communication/publish", json={
        "source": "a", "target": "advisor", "content": "para advisor"
    })
    client.post("/communication/publish", json={
        "source": "a", "target": "other", "content": "para outro"
    })
    resp = client.get("/communication/messages?target=advisor")
    msgs = resp.json()["messages"]
    assert all(m["target"] == "advisor" for m in msgs)
