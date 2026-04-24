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
        self.response_queue: list[_FakeResponse] = []

    def post(self, url: str, json: dict, timeout: int) -> _FakeResponse:
        """Armazena request e devolve resposta configurada."""
        self.requests.append((url, json, timeout))
        if self.response_queue:
            return self.response_queue.pop(0)
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


def test_generate_usa_gpu0_quando_forcado_por_padrao(
    fake_httpx: list[_FakeClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solicitacao explicitamente expert deve usar GPU0 com modelo primario."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    client = oc.OllamaClient()
    result = client.generate("revise este código", num_predict=16, small_request=False)

    assert result == {"ok": True}
    assert fake_httpx[0].base_url == "http://192.168.15.2:11434"
    url, payload, timeout = fake_httpx[0].requests[0]
    assert url == "/api/generate"
    assert payload["model"] == "qwen2.5:3b"
    assert payload["prompt"] == "revise este código"
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


def test_generate_auto_rota_request_curta_para_gpu1(
    fake_httpx: list[_FakeClient],
) -> None:
    """Request curta e simples deve ir automaticamente para GPU1."""
    client = oc.OllamaClient()
    result = client.generate("resuma em uma linha", num_predict=32, num_ctx=1024)

    assert result == {"ok": True}
    assert len(fake_httpx) == 2
    assert fake_httpx[1].base_url == "http://192.168.15.2:11435"
    _, payload, _ = fake_httpx[1].requests[0]
    assert payload["model"] == "qwen3:0.6b"


def test_generate_auto_mantem_gpu0_para_pedido_expert(
    fake_httpx: list[_FakeClient],
) -> None:
    """Pedido expert não deve ser desviado para GPU1."""
    client = oc.OllamaClient()
    result = client.generate("debug this python function and explain the error", num_predict=64, num_ctx=1024)

    assert result == {"ok": True}
    assert len(fake_httpx) == 1
    _, payload, _ = fake_httpx[0].requests[0]
    assert payload["model"] == "qwen2.5:3b"


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

    result = client.generate("debug x", small_request=False)

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


def test_generate_validated_repara_quando_primeira_resposta_falha(
    fake_httpx: list[_FakeClient],
) -> None:
    """Quando validator rejeita, cliente deve reenviar prompt de reparo."""
    client = oc.OllamaClient()
    fake_httpx[0].response_queue = [
        _FakeResponse(data={"response": ""}),
        _FakeResponse(data={"response": "Resposta final válida"}),
    ]

    result = client.generate_validated(
        "Explique a causa raiz",
        validator=lambda text: (bool(text.strip()), "resposta vazia"),
        small_request=False,
    )

    assert result == "Resposta final válida"
    assert len(fake_httpx[0].requests) == 2
    _, retry_payload, _ = fake_httpx[0].requests[1]
    assert "A resposta anterior falhou na validacao" in retry_payload["prompt"]
    assert "Explique a causa raiz" in retry_payload["prompt"]


def test_generate_validated_levanta_erro_apos_esgotar_tentativas(
    fake_httpx: list[_FakeClient],
) -> None:
    """Falha persistente deve terminar com ValueError claro."""
    client = oc.OllamaClient()
    fake_httpx[0].response_queue = [
        _FakeResponse(data={"response": ""}),
        _FakeResponse(data={"response": ""}),
    ]

    with pytest.raises(ValueError, match="Falha na validacao"):
        client.generate_validated(
            "Explique a causa raiz",
            validator=lambda text: (bool(text.strip()), "resposta vazia"),
            small_request=False,
        )


def test_generate_json_remove_code_fence_e_parseia(
    fake_httpx: list[_FakeClient],
) -> None:
    """JSON dentro de fence markdown deve ser aceito."""
    client = oc.OllamaClient()
    fake_httpx[0].next_response = _FakeResponse(data={"response": "```json\n{\"ok\": true}\n```"})

    result = client.generate_json("Retorne um objeto com ok=true", small_request=False)

    assert result == {"ok": True}


def test_generate_json_tenta_novamente_quando_resposta_nao_e_json(
    fake_httpx: list[_FakeClient],
) -> None:
    """Saída inválida deve gerar um segundo pedido pedindo JSON puro."""
    client = oc.OllamaClient()
    fake_httpx[0].response_queue = [
        _FakeResponse(data={"response": "não consegui"}),
        _FakeResponse(data={"response": "{\"status\": \"ok\"}"}),
    ]

    result = client.generate_json("Retorne um status", small_request=False)

    assert result == {"status": "ok"}
    assert len(fake_httpx[0].requests) == 2
    _, retry_payload, _ = fake_httpx[0].requests[1]
    assert "Responda novamente com JSON valido e nada mais." in retry_payload["prompt"]
