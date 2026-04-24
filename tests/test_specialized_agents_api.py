"""Smoke tests para a API mínima dos specialized agents."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from specialized_agents.api import app
from specialized_agents.agent_communication_bus import clear_active_agents, get_communication_bus


@pytest.fixture(autouse=True)
def reset_communication_state():
    """Isola estado global do bus e dos agentes ativos entre testes."""
    clear_active_agents()
    get_communication_bus().clear()
    yield
    clear_active_agents()
    get_communication_bus().clear()


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP de teste para a API FastAPI."""
    return TestClient(app)


def test_agents_activate_marks_agent_as_active(client: TestClient) -> None:
    """POST /agents/{id}/activate deve registrar o agente em memória."""
    response = client.post("/agents/python/activate")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["agent_id"] == "python"
    assert "python" in data["active_agents"]


def test_communication_test_returns_local_responses(client: TestClient) -> None:
    """Broadcast de teste deve produzir ao menos uma resposta local."""
    activate_response = client.post("/agents/python/activate")
    assert activate_response.status_code == 200

    response = client.post(
        "/communication/test",
        json={
            "message": "please_respond",
            "start_responder": True,
            "wait_seconds": 0.01,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["local_responses_count"] >= 1
    assert any(item["source"] == "python" for item in data["local_responses"])


def test_communication_messages_and_stats_expose_bus_state(client: TestClient) -> None:
    """Endpoints de mensagens e stats devem refletir publicações recentes."""
    client.post("/agents/javascript/activate")
    client.post(
        "/communication/test",
        json={"message": "validation_test", "start_responder": True, "wait_seconds": 0.01},
    )

    messages_response = client.get("/communication/messages?limit=10")
    stats_response = client.get("/communication/stats")

    assert messages_response.status_code == 200
    assert stats_response.status_code == 200

    messages = messages_response.json()["messages"]
    stats = stats_response.json()

    assert len(messages) >= 2
    assert stats["total_messages"] >= 2
    assert "coordinator" in stats["by_source"]


def test_debug_communication_subscribers_returns_shape(client: TestClient) -> None:
    """Debug endpoint deve informar subscribers e agentes ativos."""
    client.post("/agents/python/activate")

    response = client.get("/debug/communication/subscribers")

    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert data["active_agents"] == ["python"]
