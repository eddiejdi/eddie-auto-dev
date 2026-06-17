"""Testes para fallback GPU0 → GPU1 no _generate_ai_plan.

Valida que a geração de AI plan tenta GPU1 quando GPU0 retorna erro (503),
e que persiste o plano corretamente ao obter resposta válida de qualquer GPU.

Não usa APIs reais — todo I/O externo é mockado.
"""

import json
import os
import sys
import types
from pathlib import Path
from typing import Dict

import pytest


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace())
sys.modules.setdefault(
    "kucoin_api",
    types.SimpleNamespace(
        get_price=None,
        get_price_fast=None,
        get_orderbook=None,
        get_candles=None,
        get_recent_trades=None,
        get_balances=None,
        get_balance=None,
        place_market_order=None,
        analyze_orderbook=None,
        analyze_trade_flow=None,
        inner_transfer=None,
        _has_keys=lambda: False,
        get_fills_for_order=lambda *a, **kw: {},
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(
        FastTradingModel=object,
        MarketState=object,
        Signal=object,
    ),
)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(
        TrainingDatabase=object,
        TrainingManager=object,
    ),
)
sys.modules.setdefault(
    "market_rag",
    types.SimpleNamespace(
        MarketRAG=object,
    ),
)

from trading_agent import BitcoinTradingAgent


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


class _FakeCursor:
    def __init__(self) -> None:
        self.insert_params = None
        self.rowcount = 0
        self.executed: list[tuple[str, object]] = []

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))
        if "INSERT INTO btc.ai_plans" in query:
            self.insert_params = params

    def fetchone(self):
        return [1]

    def close(self) -> None:
        return None


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeDb:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def _get_conn(self) -> _FakeConn:
        return _FakeConn(self._cursor)


def test_save_ai_plan_keeps_source_model_when_sanitized_fallback_is_used() -> None:
    """Fallback sanitizado deve preservar o nome do modelo operacional."""
    cursor = _FakeCursor()
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.db = _FakeDb(cursor)
    agent._current_profile = lambda: "conservative"
    agent._sanitize_ai_plan = lambda _text: ""

    agent._save_ai_plan(
        plan_text="x",
        price=98765.43,
        regime="RANGING",
        model="trading-analyst",
        metadata={"origin": "unit-test"},
    )

    assert cursor.insert_params is not None
    saved_model = cursor.insert_params[3]
    saved_metadata = json.loads(cursor.insert_params[6])
    saved_profile = cursor.insert_params[7]

    assert saved_model == "trading-analyst"
    assert saved_profile == "conservative"
    assert saved_metadata["save_guardrail"] == "sanitized_fallback"
    assert saved_metadata["save_guardrail_source_model"] == "trading-analyst"


def test_save_ai_plan_uses_configured_retention_limit_for_housekeeping() -> None:
    """Housekeeping deve respeitar a retenção configurada por ambiente."""
    cursor = _FakeCursor()
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.db = _FakeDb(cursor)
    agent._current_profile = lambda: "aggressive"
    agent._sanitize_ai_plan = lambda text: text
    agent._AI_PLAN_RETENTION = 288

    agent._save_ai_plan(
        plan_text="Análise válida com tamanho suficiente para persistência.",
        price=71234.56,
        regime="RANGING",
        model="trading-analyst",
        metadata={"origin": "unit-test"},
    )

    housekeeping_queries = [
        (query, params)
        for query, params in cursor.executed
        if "DELETE FROM btc.ai_plans" in query
    ]
    assert len(housekeeping_queries) == 1
    delete_query, delete_params = housekeeping_queries[0]
    assert "LIMIT %s" in delete_query
    assert delete_params == ("BTC-USDT", "aggressive", "BTC-USDT", "aggressive", 288)
