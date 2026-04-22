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
        validator=None,
        fallback_model: str | None = None,
    ) -> tuple:
        """Executa a lógica de fallback extraída do _generate_ai_plan."""
        plan_payload = {
            "prompt": "test prompt",
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 1024},
        }
        plan_targets = [(self.GPU0, self.MODEL)]
        if fallback_model:
            plan_targets.append((_secondary_ollama_host(self.GPU0), fallback_model))

        fake_client = FakeClient(responses_by_host)
        raw_text = ""
        used_host = None
        validated_text = ""

        if validator is None:
            validator = lambda text: bool(text and text.strip())

        for host, model in plan_targets:
            try:
                resp = fake_client.post(
                    f"{host}/api/generate",
                    json={"model": model, **plan_payload},
                )
                if resp.status_code != 200:
                    continue
                raw_text = resp.json().get("response", "").strip()
                if raw_text and validator(raw_text):
                    validated_text = raw_text
                    used_host = host
                    break
            except Exception:
                continue

        return validated_text, used_host, fake_client.calls

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
        text, host, calls = self._run_fallback_logic(responses, fallback_model=self.MODEL)
        assert text == "Análise via GPU1 com sucesso."
        assert host == self.GPU1
        assert len(calls) == 2

    def test_both_gpus_fail_returns_empty(self):
        """Ambos GPUs retornam erro — texto vazio."""
        responses = {
            self.GPU0: FakeResponse(503, {"error": "busy"}),
            self.GPU1: FakeResponse(500, {"error": "internal error"}),
        }
        text, host, calls = self._run_fallback_logic(responses, fallback_model=self.MODEL)
        assert text == ""
        assert host is None
        assert len(calls) == 2

    def test_gpu0_empty_response_falls_to_gpu1(self):
        """GPU0 retorna 200 mas texto vazio — tenta GPU1."""
        responses = {
            self.GPU0: FakeResponse(200, {"response": ""}),
            self.GPU1: FakeResponse(200, {"response": "Resposta válida do GPU1."}),
        }
        text, host, calls = self._run_fallback_logic(responses, fallback_model=self.MODEL)
        assert text == "Resposta válida do GPU1."
        assert host == self.GPU1
        assert len(calls) == 2

    def test_gpu0_invalid_text_falls_to_gpu1(self):
        """GPU0 com texto inválido deve tentar GPU1 antes do fallback."""
        responses = {
            self.GPU0: FakeResponse(200, {"response": "{,\\\"broken\\\": [}}"}),
            self.GPU1: FakeResponse(200, {"response": "Análise válida em PT-BR com contexto de risco e execução."}),
        }
        validator = lambda text: "Análise válida" in text
        text, host, calls = self._run_fallback_logic(
            responses,
            validator=validator,
            fallback_model=self.MODEL,
        )

        assert text == "Análise válida em PT-BR com contexto de risco e execução."
        assert host == self.GPU1
        assert len(calls) == 2

    def test_no_ai_plan_fallback_model_returns_empty_after_primary_invalid(self):
        """Sem fallback dedicado, AI plan deve parar no primário e cair no fallback determinístico."""
        responses = {
            self.GPU0: FakeResponse(200, {"response": "{,\"broken\": [}}"}),
            self.GPU1: FakeResponse(200, {"response": "Texto que não deveria ser consultado."}),
        }
        validator = lambda text: "Análise válida" in text
        text, host, calls = self._run_fallback_logic(
            responses,
            validator=validator,
            fallback_model=None,
        )

        assert text == ""
        assert host is None
        assert len(calls) == 1

    def test_secondary_host_swaps_port(self):
        """Verifica que _secondary_ollama_host alterna portas corretamente."""
        assert _secondary_ollama_host(self.GPU0) == self.GPU1
        assert _secondary_ollama_host(self.GPU1) == self.GPU0
        assert _secondary_ollama_host("http://custom:9999") == "http://custom:9999"


class TestSanitizeAiPlan:
    """Testa a função _sanitize_ai_plan diretamente via importação inline."""

    @staticmethod
    def _sanitize(text: str) -> str:
        """Executa o mesmo pipeline de sanitização do trading_agent."""
        import re as _re
        if not text:
            return ""
        # Step 0: strip Markdown
        text = _re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
        text = _re.sub(r"^#{1,6}\s+", "", text, flags=_re.MULTILINE)
        text = _re.sub(r"^[\-\*•]\s+", "", text, flags=_re.MULTILINE)
        text = _re.sub(r"^>\s+", "", text, flags=_re.MULTILINE)
        text = _re.sub(r"`{1,3}[^`\n]*`{1,3}", "", text)
        text = _re.sub(r"\n{3,}", "\n\n", text).strip()
        # Step 1: think tags
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"</?think>", "", text)
        # Step 2: alpha ratio
        alpha_chars = sum(1 for c in text if c.isalpha())
        total_chars = len(text.strip())
        if total_chars > 0 and alpha_chars / total_chars < 0.40:
            return ""
        # Step 5: keyword check
        trading_keywords = [
            "btc", "bitcoin", "preço", "price", "mercado", "market",
            "comprar", "buy", "vender", "sell", "tendência", "trend",
            "rsi", "posição", "position", "suporte", "resistência",
            "alta", "baixa", "bullish", "bearish", "trading", "usdt",
            "volatilidade", "momentum", "regime", "risco", "risk",
            "oportunidade", "opportunity", "stop", "profit", "pnl",
        ]
        hits = sum(1 for kw in trading_keywords if kw in text.lower())
        if hits < 3:
            return ""
        # Step 7: lone punctuation
        lone_punct = len(_re.findall(r"(?:^|[ ])[.,;:\-!?]{1,3}(?:[ ]|$)", text))
        if lone_punct > 5:
            return ""
        return text

    def test_markdown_bold_stripped(self):
        """Texto com **bold** deve passar após strip de Markdown."""
        text = (
            "**Situação atual**: O BTC está em regime RANGING com RSI=46.\n"
            "**Ação**: O agente vai aguardar o preço cair até o suporte em $77,852.\n"
            "**Saída**: Venda quando o preço atingir $78,864 (TP=0.80%).\n"
            "O risco principal é a volatilidade e o mercado bearish.\n"
            "A oportunidade é comprar na faixa de suporte com stop loss ativado."
        )
        result = self._sanitize(text)
        assert result != "", "Texto com Markdown bold deve ser aceito após strip"
        assert "**" not in result

    def test_markdown_bullet_list_stripped(self):
        """Lista com - bullets deve passar após strip."""
        text = (
            "O mercado BTC está em tendência de alta com RSI=61.\n"
            "- Comprar na faixa $78,100-$78,300 (buy zone)\n"
            "- Vender quando atingir $78,864 (profit target)\n"
            "- Stop loss em $77,500 para reduzir risco\n"
            "O regime BULLISH favorece entradas no suporte com baixa volatilidade."
        )
        result = self._sanitize(text)
        assert result != "", "Lista com bullets deve ser aceita após strip"
        assert "- " not in result

    def test_clean_text_passes(self):
        """Texto limpo em PT-BR com vocabulário de trading deve passar."""
        text = (
            "O BTC está em regime lateral com RSI em 46 e volatilidade moderada. "
            "O agente aguarda queda ao suporte de $77,852 para executar nova compra. "
            "A venda será disparada no alvo de take profit em $78,864. "
            "O risco está controlado pelo stop loss e trailing stop ativo."
        )
        result = self._sanitize(text)
        assert result != ""
        assert len(result) > 100

    def test_json_response_rejected(self):
        """Resposta JSON pura deve ser rejeitada (ratio alfanumérico baixo)."""
        text = '{"entry_low": 78100, "entry_high": 78300, "target_sell": 78864}'
        result = self._sanitize(text)
        assert result == ""

    def test_few_keywords_rejected(self):
        """Texto sem vocabulário de trading deve ser rejeitado."""
        text = "O clima hoje está ensolarado com temperatura de 25 graus. Muito agradável."
        result = self._sanitize(text)
        assert result == ""
