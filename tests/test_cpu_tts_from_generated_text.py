from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
MODULE_PATH = TOOLS_DIR / "test_cpu_tts_from_generated_text.py"
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("test_cpu_tts_from_generated_text_tool", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
tts_tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tts_tool)


class _FakeOllamaClient:
    responses_by_model: dict[str, list[object]] = {}
    attempts: list[str] = []

    def __init__(self, host: str, model: str, keep_alive: str | None = None) -> None:
        self.host = host
        self.model = model
        self.keep_alive = keep_alive

    def generate_validated(self, prompt: str, **kwargs) -> str:
        del prompt, kwargs
        _FakeOllamaClient.attempts.append(self.model)
        response_queue = _FakeOllamaClient.responses_by_model[self.model]
        result = response_queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return str(result)

    def close(self) -> None:
        return None


def test_clean_generated_text_remove_think_and_fences() -> None:
    raw = "```markdown\n<think>interno</think> Texto final  útil. \n```"

    cleaned = tts_tool.clean_generated_text(raw)

    assert cleaned == "interno Texto final útil."


def test_iter_gpu1_models_preserva_ordem_e_remove_duplicatas() -> None:
    models = tts_tool.iter_gpu1_models(
        "gemma3:1b",
        "llama3.2:1b, gemma3:1b",
    )

    assert models == ["gemma3:1b", "llama3.2:1b"]


def test_generate_with_gpu1_models_usa_fallback_quando_modelo_primario_falha(monkeypatch) -> None:
    _FakeOllamaClient.responses_by_model = {
        "gemma3:1b": [RuntimeError("server busy, please try again. maximum pending requests exceeded")],
        "llama3.2:1b": ["Texto final de teste, com contexto suficiente e tres frases. Segunda frase aqui. Terceira frase aqui."],
    }
    _FakeOllamaClient.attempts = []
    monkeypatch.setattr(tts_tool, "OllamaClient", _FakeOllamaClient)

    result = tts_tool.generate_with_gpu1_models(
        prompt="prompt teste",
        host="http://gpu1:11435",
        primary_model="gemma3:1b",
        fallback_models_arg="llama3.2:1b",
        validator=lambda text: (bool(text.strip()), "vazio"),
        num_predict=128,
        num_ctx=1024,
        max_rounds=1,
        retry_wait_seconds=0,
    )

    assert "Texto final de teste" in result
    assert _FakeOllamaClient.attempts == ["gemma3:1b", "llama3.2:1b"]


def test_build_gpu1_expansion_prompt_exige_contexto_de_autoria_e_relatoria() -> None:
    prompt = tts_tool.build_gpu1_expansion_prompt("Texto-base curto.")

    assert "/no_think" in prompt
    assert "se houver materia de autoria do senador" in prompt
    assert "se houver materia sob relatoria" in prompt


def test_generate_with_llm_chain_tenta_segundo_endpoint(monkeypatch) -> None:
    class _FakeOllamaClient:
        attempts: list[tuple[str, str]] = []

        def __init__(self, host: str, model: str, keep_alive: str | None = None) -> None:
            self.host = host
            self.model = model

        def generate_validated(self, prompt: str, **kwargs) -> str:
            del prompt, kwargs
            _FakeOllamaClient.attempts.append((self.host, self.model))
            if self.host.endswith(":11434"):
                raise RuntimeError("gpu0 offline")
            return "Texto final de teste, com contexto suficiente e tres frases. Segunda frase aqui. Terceira frase aqui."

        def close(self) -> None:
            return None

    _FakeOllamaClient.attempts = []
    monkeypatch.setattr(tts_tool, "OllamaClient", _FakeOllamaClient)

    text, endpoint = tts_tool.generate_with_llm_chain(
        prompt="prompt teste",
        endpoints=(
            {"name": "gpu0", "host": "http://gpu0:11434", "model": "mistral:7b", "fallback_models": ""},
            {"name": "gpu1", "host": "http://gpu1:11435", "model": "gemma3:1b", "fallback_models": ""},
        ),
        validator=lambda candidate: (bool(candidate.strip()), "vazio"),
        num_predict=128,
        num_ctx=1024,
        max_rounds=1,
        retry_wait_seconds=0,
    )

    assert "Texto final de teste" in text
    assert endpoint == "gpu1:gemma3:1b"
    assert _FakeOllamaClient.attempts[0] == ("http://gpu0:11434", "mistral:7b")
    assert _FakeOllamaClient.attempts[1] == ("http://gpu1:11435", "gemma3:1b")
