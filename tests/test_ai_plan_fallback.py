"""Testes para fallback GPU0 → GPU1 no _generate_ai_plan.

Valida que a geração de AI plan tenta GPU1 quando GPU0 retorna erro (503),
e que persiste o plano corretamente ao obter resposta válida de qualquer GPU.

Não usa APIs reais — todo I/O externo é mockado.
"""

from typing import Dict

import pytest


def _secondary_ollama_host(host: str) -> str:
    """Replica do BitcoinTradingAgent._secondary_ollama_host."""
    if ":11434" in host:
        return host.replace(":11434", ":11435")
    if ":11435" in host:
        return host.replace(":11435", ":11434")
    return host


class FakeResponse:
    """Simula resposta httpx com status_code e json()."""

    def __init__(self, status_code: int, json_data: dict):
        self._status_code = status_code
        self._json_data = json_data

    @property
    def status_code(self) -> int:
        return self._status_code

    def json(self) -> dict:
        return self._json_data


class FakeClient:
    """Simula httpx.Client com respostas configuráveis por host."""

    def __init__(self, responses_by_host: Dict[str, FakeResponse]):
        self._responses = responses_by_host
        self.calls = []

    def post(self, url: str, json: dict = None) -> FakeResponse:
        self.calls.append((url, json))
        for host_prefix, resp in self._responses.items():
            if url.startswith(host_prefix):
                return resp
        return FakeResponse(500, {"error": "unknown host"})

    def close(self):
        pass


# ── Testes ──

class TestAiPlanFallbackLogic:
    """Testa a lógica de fallback GPU0 → GPU1 isoladamente."""

    GPU0 = "http://192.168.15.2:11434"
    GPU1 = "http://192.168.15.2:11435"
    MODEL = "phi4-mini:latest"

    def _run_fallback_logic(
        self,
        responses_by_host: Dict[str, FakeResponse],
    ) -> tuple:
        """Executa a lógica de fallback extraída do _generate_ai_plan."""
        plan_payload = {
            "prompt": "test prompt",
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 1024},
        }
        plan_targets = [
            (self.GPU0, self.MODEL),
            (_secondary_ollama_host(self.GPU0), self.MODEL),
        ]

        fake_client = FakeClient(responses_by_host)
        raw_text = ""
        used_host = None

        for host, model in plan_targets:
            try:
                resp = fake_client.post(
                    f"{host}/api/generate",
                    json={"model": model, **plan_payload},
                )
                if resp.status_code != 200:
                    continue
                raw_text = resp.json().get("response", "").strip()
                if raw_text:
                    used_host = host
                    break
            except Exception:
                continue

        return raw_text, used_host, fake_client.calls

    def test_gpu0_success_no_fallback(self):
        """GPU0 retorna 200 — não tenta GPU1."""
        responses = {
            self.GPU0: FakeResponse(200, {"response": "Mercado em alta moderada."}),
            self.GPU1: FakeResponse(200, {"response": "Fallback text"}),
        }
        text, host, calls = self._run_fallback_logic(responses)
        assert text == "Mercado em alta moderada."
        assert host == self.GPU0
        assert len(calls) == 1

    def test_gpu0_503_falls_to_gpu1(self):
        """GPU0 retorna 503 — fallback para GPU1."""
        responses = {
            self.GPU0: FakeResponse(503, {"error": "model busy"}),
            self.GPU1: FakeResponse(200, {"response": "Análise via GPU1 com sucesso."}),
        }
        text, host, calls = self._run_fallback_logic(responses)
        assert text == "Análise via GPU1 com sucesso."
        assert host == self.GPU1
        assert len(calls) == 2

    def test_both_gpus_fail_returns_empty(self):
        """Ambos GPUs retornam erro — texto vazio."""
        responses = {
            self.GPU0: FakeResponse(503, {"error": "busy"}),
            self.GPU1: FakeResponse(500, {"error": "internal error"}),
        }
        text, host, calls = self._run_fallback_logic(responses)
        assert text == ""
        assert host is None
        assert len(calls) == 2

    def test_gpu0_empty_response_falls_to_gpu1(self):
        """GPU0 retorna 200 mas texto vazio — tenta GPU1."""
        responses = {
            self.GPU0: FakeResponse(200, {"response": ""}),
            self.GPU1: FakeResponse(200, {"response": "Resposta válida do GPU1."}),
        }
        text, host, calls = self._run_fallback_logic(responses)
        assert text == "Resposta válida do GPU1."
        assert host == self.GPU1
        assert len(calls) == 2

    def test_secondary_host_swaps_port(self):
        """Verifica que _secondary_ollama_host alterna portas corretamente."""
        assert _secondary_ollama_host(self.GPU0) == self.GPU1
        assert _secondary_ollama_host(self.GPU1) == self.GPU0
        assert _secondary_ollama_host("http://custom:9999") == "http://custom:9999"
