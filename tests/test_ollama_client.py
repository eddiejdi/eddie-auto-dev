"""Testes unitarios para tools/ollama_client.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Adicionar tools/ ao path para import direto
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
MODULE_PATH = TOOLS_DIR / "ollama_client.py"
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("ollama_client", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
oc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(oc)


class _FakeResponse:
    """Resposta fake para simular httpx.Response."""

    def __init__(self, *, data: dict | None = None, text: str = "", raises_json: bool = False) -> None:
        self._data = data or {}
        self.text = text
        self._raises_json = raises_json

    def raise_for_status(self) -> None:
        """Mantem compatibilidade com interface de resposta."""
        return None

    def json(self) -> dict:
        """Retorna JSON fake ou levanta erro de decode."""
        if self._raises_json:
            raise json.JSONDecodeError("bad", self.text, 0)
        return self._data


class _FakeClient:
    """Cliente fake para capturar chamadas POST."""

    def __init__(self, *, base_url: str, timeout: float) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.closed = False
        self.requests: list[tuple[str, dict, int]] = []
        self.next_response = _FakeResponse(data={"ok": True})

    def post(self, url: str, json: dict, timeout: int) -> _FakeResponse:
        """Armazena request e devolve resposta configurada."""
        self.requests.append((url, json, timeout))
        return self.next_response

    def close(self) -> None:
        """Marca cliente como fechado."""
        self.closed = True


@pytest.fixture
def fake_httpx(monkeypatch: pytest.MonkeyPatch) -> list[_FakeClient]:
    """Substitui httpx.Client por fake e retorna instancias criadas."""
    clients: list[_FakeClient] = []

    class _FakeHttpxModule:
        """Modulo fake com Client compativel."""

        @staticmethod
        def Client(base_url: str, timeout: float) -> _FakeClient:  # noqa: N802
            client = _FakeClient(base_url=base_url, timeout=timeout)
            clients.append(client)
            return client

    monkeypatch.setattr(oc, "httpx", _FakeHttpxModule)
    return clients


def test_generate_usa_gpu0_phi_por_padrao(
    fake_httpx: list[_FakeClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solicitacao padrao deve usar GPU0 com modelo Phi."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    client = oc.OllamaClient()
    result = client.generate("teste", num_predict=16)

    assert result == {"ok": True}
    assert fake_httpx[0].base_url == "http://192.168.15.2:11434"
    url, payload, timeout = fake_httpx[0].requests[0]
    assert url == "/api/generate"
    assert payload["model"] == "phi4-mini:latest"
    assert payload["prompt"] == "teste"
    assert timeout == 300


def test_generate_small_request_usa_gpu1_modelo_pequeno(
    fake_httpx: list[_FakeClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solicitacao pequena deve rotear para GPU1 por default."""
    monkeypatch.delenv("OLLAMA_HOST_GPU1", raising=False)
    monkeypatch.delenv("OLLAMA_SMALL_MODEL", raising=False)

    client = oc.OllamaClient()
    result = client.generate("curto", small_request=True)

    assert result == {"ok": True}
    assert len(fake_httpx) == 2
    assert fake_httpx[1].base_url == "http://192.168.15.2:11435"
    _, payload, _ = fake_httpx[1].requests[0]
    assert payload["model"] == "qwen3:0.6b"


def test_generate_aceita_override_explicito(
    fake_httpx: list[_FakeClient],
) -> None:
    """Host e modelo explicitos devem ter prioridade."""
    client = oc.OllamaClient()
    _ = client.generate(
        "override",
        host="http://custom:11434",
        model="phi-custom",
        small_request=True,
    )

    assert len(fake_httpx) == 2
    assert fake_httpx[1].base_url == "http://custom:11434"
    _, payload, _ = fake_httpx[1].requests[0]
    assert payload["model"] == "phi-custom"


def test_generate_fallback_para_response_text_quando_json_invalido(
    fake_httpx: list[_FakeClient],
) -> None:
    """Quando resposta nao e JSON, retorna response_text."""
    client = oc.OllamaClient()
    fake_httpx[0].next_response = _FakeResponse(text="raw-content", raises_json=True)

    result = client.generate("x")

    assert result == {"response_text": "raw-content"}


def test_close_fecha_todos_os_clients(fake_httpx: list[_FakeClient]) -> None:
    """close deve fechar todos os clientes cacheados."""
    client = oc.OllamaClient()
    _ = client.generate("a", small_request=True)

    client.close()

    assert all(c.closed for c in fake_httpx)


def test_init_falha_sem_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem modulo httpx disponivel, inicializacao falha claramente."""
    monkeypatch.setattr(oc, "httpx", None)

    with pytest.raises(RuntimeError, match="httpx nao esta instalado|httpx não está instalado"):
        _ = oc.OllamaClient()
