"""Testes da integração Hugging Face Inference API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from specialized_agents.api import app


class _FakeHFClient:
    async def list_available_resources(self) -> dict[str, object]:
        return {
            "enabled": True,
            "provider": "huggingface-inference-api",
            "remote_text_to_image_models": [{"id": "stabilityai/sdxl-turbo"}],
        }

    async def generate_image(self, request) -> dict[str, object]:
        return {
            "success": True,
            "provider": "huggingface-inference-api",
            "model": request.model or "stabilityai/stable-diffusion-xl-base-1.0",
            "bytes": 10,
            "file_path": None,
            "image_base64": "ZmFrZQ==",
        }


class _ErrorHFClient:
    async def list_available_resources(self) -> dict[str, object]:
        raise RuntimeError("falha recursos")

    async def generate_image(self, request) -> dict[str, object]:
        raise RuntimeError("falha imagem")


def test_huggingface_resources_endpoint_success(monkeypatch) -> None:
    """Endpoint de recursos deve responder dados do cliente Hugging Face."""
    import specialized_agents.huggingface_inference_agent as hf_module

    monkeypatch.setattr(hf_module, "get_huggingface_client", lambda: _FakeHFClient())
    client = TestClient(app)

    response = client.get("/huggingface/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider"] == "huggingface-inference-api"
    assert data["remote_text_to_image_models"][0]["id"] == "stabilityai/sdxl-turbo"


def test_huggingface_generate_image_endpoint_success(monkeypatch) -> None:
    """Endpoint de geração de imagem deve retornar payload de sucesso."""
    import specialized_agents.huggingface_inference_agent as hf_module

    monkeypatch.setattr(hf_module, "get_huggingface_client", lambda: _FakeHFClient())
    client = TestClient(app)

    response = client.post(
        "/huggingface/image/generate",
        json={
            "prompt": "cidade futurista ao amanhecer",
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
    assert data["success"] is True
    assert data["model"] == "stabilityai/sdxl-turbo"
    assert data["image_base64"] == "ZmFrZQ=="


def test_huggingface_generate_image_endpoint_error(monkeypatch) -> None:
    """Endpoint deve retornar HTTP 500 quando o cliente falhar."""
    import specialized_agents.huggingface_inference_agent as hf_module

    monkeypatch.setattr(hf_module, "get_huggingface_client", lambda: _ErrorHFClient())
    client = TestClient(app)

    response = client.post(
        "/huggingface/image/generate",
        json={"prompt": "teste"},
    )

    assert response.status_code == 500
    assert "falha imagem" in response.json()["detail"]
