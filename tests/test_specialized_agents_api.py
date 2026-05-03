"""Smoke tests para a API mínima dos specialized agents."""

from __future__ import annotations

import sys
from types import ModuleType

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


def test_nextcloud_access_panel_is_served_on_base_path(client: TestClient) -> None:
    """Painel do Nextcloud deve responder na raiz publica do prefixo."""
    response = client.get("/nextcloud-access/")

    assert response.status_code == 200
    assert "Painel de criação de acesso ao Nextcloud" in response.text


def test_orchestrator_media_resources_returns_hf_resources(client: TestClient, monkeypatch) -> None:
    """Orquestrador deve consolidar recursos de mídia via integração Hugging Face."""
    import specialized_agents.api as api_module

    fake_module = ModuleType("specialized_agents.huggingface_inference_agent")

    class _FakeHFClient:
        async def list_available_resources(self) -> dict[str, object]:
            return {
                "enabled": True,
                "provider": "huggingface-inference-api",
                "remote_text_to_image_models": [{"id": "stabilityai/sdxl-turbo"}],
            }

    fake_module.get_huggingface_client = lambda: _FakeHFClient()
    monkeypatch.setitem(sys.modules, "specialized_agents.huggingface_inference_agent", fake_module)
    monkeypatch.setattr(
        api_module,
        "get_communication_bus",
        lambda: get_communication_bus(),
    )

    response = client.get("/orchestrator/media/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["orchestrator"] == "gpu0"
    assert data["provider"] == "huggingface-inference-api"
    assert data["resources"]["remote_text_to_image_models"][0]["id"] == "stabilityai/sdxl-turbo"


def test_orchestrator_media_generate_image_routes_to_hf(client: TestClient, monkeypatch) -> None:
    """Orquestrador deve delegar geração de imagem para o agente Hugging Face."""
    fake_module = ModuleType("specialized_agents.huggingface_inference_agent")

    class _FakeHFClient:
        async def generate_image(self, request):
            return {
                "success": True,
                "provider": "huggingface-inference-api",
                "model": request.model or "stabilityai/stable-diffusion-xl-base-1.0",
                "image_base64": "ZmFrZQ==",
            }

    class _FakeHFRequest:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_module.get_huggingface_client = lambda: _FakeHFClient()
    fake_module.HFImageGenerateRequest = _FakeHFRequest
    monkeypatch.setitem(sys.modules, "specialized_agents.huggingface_inference_agent", fake_module)

    response = client.post(
        "/orchestrator/media/image/generate",
        json={
            "prompt": "floresta encantada com neblina",
            "model": "stabilityai/sdxl-turbo",
            "width": 512,
            "height": 512,
            "steps": 4,
            "guidance_scale": 3.0,
            "save_to_disk": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["orchestrator"] == "gpu0"
    assert data["provider"] == "huggingface-inference-api"
    assert data["result"]["success"] is True
    assert data["result"]["model"] == "stabilityai/sdxl-turbo"
