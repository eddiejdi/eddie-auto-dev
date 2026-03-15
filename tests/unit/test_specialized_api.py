from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _load_module(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_HOST", "http://ollama.test:11435")
    monkeypatch.setenv("OLLAMA_BACKGROUND_MODEL", "qwen3:0.6b")
    import specialized_agents.api as api_module

    return importlib.reload(api_module)


def test_health_exposes_ollama_settings(monkeypatch):
    module = _load_module(monkeypatch)
    client = TestClient(module.app, raise_server_exceptions=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ollama_host"] == "http://ollama.test:11435"
    assert response.json()["ollama_model"] == "qwen3:0.6b"


def test_llm_tools_chat_proxies_to_ollama(monkeypatch):
    module = _load_module(monkeypatch)
    client = TestClient(module.app, raise_server_exceptions=False)
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "<svg viewBox='0 0 10 10'></svg>"}

    def fake_post(url, json, timeout):
        calls["url"] = url
        calls["json"] = json
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(module.requests, "post", fake_post)

    response = client.post(
        "/llm-tools/chat",
        json={
            "prompt": "Generate SVG",
            "conversation_id": "bg-check",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "<svg viewBox='0 0 10 10'></svg>"
    assert response.json()["conversation_id"] == "bg-check"
    assert calls["url"] == "http://ollama.test:11435/api/generate"
    assert calls["json"]["model"] == "qwen3:0.6b"
    assert calls["json"]["stream"] is False
