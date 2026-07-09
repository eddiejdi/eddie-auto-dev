#!/usr/bin/env python3
"""Regressões para a janela fresca de trade gerada em background."""

from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys
import time
import types

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace())
# Stub numpy — apenas atributos necessários para pytest.approx e imports internos
import unittest.mock as _mock
_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)
_psycopg2_mock = types.ModuleType("psycopg2")
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(
        TrainingDatabase=object,
        TrainingManager=object,
    ),
)
sys.modules.setdefault(
    "market_rag",
    types.SimpleNamespace(MarketRAG=object),
)
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
    _resolve_telegram_bot_token=lambda: "",
    _resolve_telegram_chat_id=lambda: "",
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

import trading_agent
from trading_agent import BitcoinTradingAgent
from llm import LLMRouter


def _router_agent(profile: str = "aggressive") -> BitcoinTradingAgent:
    """Agent com um LLMRouter real injetado (sem endpoints extras).

    _request_ollama_structured hoje só delega para self._llm.request_structured;
    o roteamento primary/fallback/retry vive no LLMRouter (llm.py). Os testes
    abaixo exercitam esse caminho stubando router._do_generate.
    """
    agent = _agent(profile)
    router = LLMRouter()
    router._endpoints = []  # sem terceiro-tier: só os pares explícitos são tentados
    agent._llm = router
    return agent


def _agent(profile: str = "aggressive") -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.config_name = f"config_BTC_USDT_{profile}.json"
    agent.state = SimpleNamespace(profile=profile)
    agent._load_live_config = lambda: {"profile": profile}
    return agent


def _controls(min_confidence: float = 0.61, min_trade_interval: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        min_confidence=min_confidence,
        min_trade_interval=min_trade_interval,
    )


def _rag(price: float = 70700.0, tp_pct: float = 0.004) -> SimpleNamespace:
    return SimpleNamespace(
        ai_buy_target_price=price,
        ai_take_profit_pct=tp_pct,
        suggested_regime="RANGING",
    )


def test_parse_ai_trade_window_clamps_outlier_payloads() -> None:
    agent = _agent("aggressive")
    market_state = SimpleNamespace(price=70800.0)

    raw = json.dumps(
        {
            "entry_low": 68000,
            "entry_high": 72000,
            "target_sell": 80000,
            "min_confidence": 0.10,
            "min_trade_interval": 5,
            "ttl_seconds": 9999,
            "rationale": "stress",
        }
    )

    suggestion = agent._parse_ai_trade_window(raw, market_state, _rag(), _controls())

    assert suggestion.entry_low >= (70800.0 * (1 - 0.0035)) - 0.01
    assert suggestion.entry_high <= (70800.0 * (1 + 0.0016)) + 0.01
    assert suggestion.target_sell <= (70800.0 * (1 + 0.0120)) + 0.01
    assert suggestion.min_confidence == pytest.approx(0.51)
    assert suggestion.min_trade_interval == 75
    assert suggestion.ttl_seconds == 90


def test_extract_json_object_repairs_python_dict_payload() -> None:
    parsed = BitcoinTradingAgent._extract_json_object(
        "{'entry_low': 70000.0, 'entry_high': 70010.0, 'ttl_seconds': 45}"
    )

    assert parsed["entry_low"] == pytest.approx(70000.0)
    assert parsed["entry_high"] == pytest.approx(70010.0)
    assert parsed["ttl_seconds"] == 45


def test_extract_json_object_repairs_truncated_json() -> None:
    parsed = BitcoinTradingAgent._extract_json_object(
        'noise {"entry_low":70000.0,"entry_high":70010.0,"ttl_seconds":45,'
    )

    assert parsed["entry_low"] == pytest.approx(70000.0)
    assert parsed["entry_high"] == pytest.approx(70010.0)
    assert parsed["ttl_seconds"] == 45


def test_parse_ai_trade_window_recovers_numeric_fields_from_broken_json() -> None:
    agent = _agent("conservative")
    market_state = SimpleNamespace(price=70800.0)

    raw = (
        '{"entry_low":70790.0,"entry_high":70805.0,"target_sell":70920.0,'
        '"min_confidence":0.63,"min_trade_interval":180,"ttl_seconds":90,'
        '"rationale":["broken"}'
    )

    suggestion = agent._parse_ai_trade_window(raw, market_state, _rag(), _controls())

    assert suggestion.entry_low == pytest.approx(70790.0)
    assert suggestion.entry_high == pytest.approx(70805.0)
    assert suggestion.target_sell >= 70920.0
    assert suggestion.min_confidence == pytest.approx(0.63)
    assert suggestion.min_trade_interval == 180
    assert suggestion.ttl_seconds == 90


def test_parse_ai_trade_controls_recovers_numeric_fields_from_broken_json() -> None:
    agent = _agent("aggressive")

    suggestion = agent._parse_ai_trade_controls(
        '{"min_confidence":0.59,"min_trade_interval":210,"max_position_pct":0.25,'
        '"max_positions":3,"min_sell_pnl_pct":0.004,"rationale":["broken"}'
    )

    assert suggestion.min_confidence == pytest.approx(0.59)
    assert suggestion.min_trade_interval == 210
    assert suggestion.max_position_pct == pytest.approx(0.25)
    assert suggestion.max_positions == 3
    assert suggestion.min_sell_pnl_pct == pytest.approx(0.004)


def test_parse_ai_trade_controls_min_sell_pnl_clamps() -> None:
    """min_sell_pnl_pct deve ser limitado entre 0.002 e 0.010."""
    agent = _agent("aggressive")

    # Abaixo do floor → clampado para 0.002
    s_low = agent._parse_ai_trade_controls(
        '{"min_confidence":0.60,"min_trade_interval":300,"max_position_pct":0.5,'
        '"max_positions":4,"min_sell_pnl_pct":0.0001}'
    )
    assert s_low.min_sell_pnl_pct == pytest.approx(0.002)

    # Acima do ceiling → clampado para 0.010
    s_high = agent._parse_ai_trade_controls(
        '{"min_confidence":0.60,"min_trade_interval":300,"max_position_pct":0.5,'
        '"max_positions":4,"min_sell_pnl_pct":0.05}'
    )
    assert s_high.min_sell_pnl_pct == pytest.approx(0.010)

    # Dentro do range → mantido
    s_ok = agent._parse_ai_trade_controls(
        '{"min_confidence":0.60,"min_trade_interval":300,"max_position_pct":0.5,'
        '"max_positions":4,"min_sell_pnl_pct":0.003}'
    )
    assert s_ok.min_sell_pnl_pct == pytest.approx(0.003)


def test_parse_ai_trade_controls_min_sell_pnl_fallback_when_missing() -> None:
    """Se Ollama não retornar min_sell_pnl_pct, usa valor do config (default 0.003)."""
    agent = _agent("conservative")

    suggestion = agent._parse_ai_trade_controls(
        '{"min_confidence":0.62,"min_trade_interval":400,"max_position_pct":0.4,"max_positions":2}'
    )

    # sem min_sell_pnl_pct no JSON → deve usar o default do config (0.003) ou floor
    assert 0.002 <= suggestion.min_sell_pnl_pct <= 0.010


def test_get_fresh_ai_trade_window_returns_none_when_stale(tmp_path: Path) -> None:
    agent = _agent("conservative")
    window_file = tmp_path / "trade_window_conservative.json"
    window_file.write_text(
        json.dumps(
            {
                "current": {
                    "symbol": "BTC-USDT",
                    "profile": "conservative",
                    "entry_low": 70000,
                    "entry_high": 70010,
                    "valid_until": time.time() - 1,
                }
            }
        )
    )
    agent._get_trade_window_file = lambda: window_file

    assert agent._get_fresh_ai_trade_window() is None


def test_resolve_buy_gate_limits_uses_fresh_window_ceiling() -> None:
    agent = _agent("aggressive")
    agent._get_buy_extra_discount_pct = lambda rag_adj, signal=None: 0.0
    agent._get_buy_target_uplift_pct = lambda rag_adj, signal=None: 0.0
    agent._get_buy_target_tolerance_pct = lambda rag_adj, signal=None: 0.0
    agent._get_fresh_ai_trade_window = lambda: {
        "symbol": "BTC-USDT",
        "profile": "aggressive",
        "entry_low": 100.00,
        "entry_high": 100.12,
        "valid_until": time.time() + 45,
    }

    limits = agent._resolve_buy_gate_limits(
        SimpleNamespace(ai_buy_target_price=100.0),
        SimpleNamespace(action="BUY", price=100.10, confidence=0.70, reason="news:bullish"),
    )

    assert limits["effective_buy_target"] == pytest.approx(100.0)
    assert limits["effective_buy_ceiling"] == pytest.approx(100.12)
    assert limits["used_trade_window"] is True


def test_resolve_buy_gate_limits_falls_back_when_window_missing() -> None:
    agent = _agent("aggressive")
    agent._get_buy_extra_discount_pct = lambda rag_adj, signal=None: 0.0
    agent._get_buy_target_uplift_pct = lambda rag_adj, signal=None: 0.0008
    agent._get_buy_target_tolerance_pct = lambda rag_adj, signal=None: 0.0008
    agent._get_fresh_ai_trade_window = lambda: None

    limits = agent._resolve_buy_gate_limits(
        SimpleNamespace(ai_buy_target_price=100.0),
        SimpleNamespace(action="BUY", price=100.10, confidence=0.70, reason="news:bullish"),
    )

    expected_target = 100.0 * (1 + 0.0008)
    expected_ceiling = expected_target * (1 + 0.0008)
    assert limits["effective_buy_target"] == pytest.approx(expected_target)
    assert limits["effective_buy_ceiling"] == pytest.approx(expected_ceiling)
    assert limits["used_trade_window"] is False


def test_buy_target_tolerance_pct_expands_for_aggressive_bullish_entries() -> None:
    agent = _agent("aggressive")
    rag_adj = _rag()
    rag_adj.suggested_regime = "BULLISH"
    signal = SimpleNamespace(
        action="BUY",
        price=70000.0,
        confidence=0.65,
        reason="news:bullish bid pressure buying pressure",
    )

    assert agent._get_buy_target_tolerance_pct(rag_adj, signal) == pytest.approx(0.0030)


def test_buy_target_uplift_pct_increases_for_aggressive_bullish_entries() -> None:
    agent = _agent("aggressive")
    rag_adj = _rag()
    rag_adj.suggested_regime = "BULLISH"
    signal = SimpleNamespace(
        action="BUY",
        price=70000.0,
        confidence=0.65,
        reason="news:bullish bid pressure buying pressure",
    )

    assert agent._get_buy_target_uplift_pct(rag_adj, signal) == pytest.approx(0.0020)


def test_buy_target_tolerance_pct_allows_conservative_oversold_reversal() -> None:
    agent = _agent("conservative")
    rag_adj = _rag()
    rag_adj.suggested_regime = "RANGING"
    signal = SimpleNamespace(
        action="BUY",
        price=70000.0,
        confidence=0.68,
        reason="rsi oversold",
    )

    assert agent._get_buy_target_tolerance_pct(rag_adj, signal) == pytest.approx(0.0015)


def test_trade_window_targets_use_secondary_on_conservative_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_FALLBACK_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", raising=False)
    agent = _agent("conservative")
    agent._OLLAMA_TRADE_WINDOW_HOST = "http://gpu0:11434"
    agent._OLLAMA_TRADE_WINDOW_MODEL = "phi4-mini:latest"
    agent._OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL = "gemma3:1b"
    agent._OLLAMA_TRADE_WINDOW_FALLBACK_MODEL = "gemma3:1b"

    primary_host, primary_model, fallback_host, fallback_model = agent._get_trade_window_ollama_targets()

    assert primary_host.endswith(":11435")
    assert primary_model == "gemma3:1b"
    assert fallback_host == ""
    assert fallback_model == ""


def test_trade_window_targets_prefer_secondary_on_gpu1_for_aggressive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_FALLBACK_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", raising=False)
    agent = _agent("aggressive")
    agent._OLLAMA_TRADE_WINDOW_HOST = "http://gpu0:11434"
    agent._OLLAMA_TRADE_WINDOW_MODEL = "phi4-mini:latest"
    agent._OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL = "gemma3:1b"
    agent._OLLAMA_TRADE_WINDOW_FALLBACK_MODEL = "gemma3:1b"

    primary_host, primary_model, fallback_host, fallback_model = agent._get_trade_window_ollama_targets()

    assert primary_host.endswith(":11435")
    assert primary_model == "gemma3:1b"
    assert fallback_host == ""
    assert fallback_model == ""


def test_trade_controls_targets_prefer_secondary_on_gpu1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TRADE_PARAMS_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TRADE_PARAMS_FALLBACK_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", raising=False)
    agent = _agent("aggressive")
    agent._OLLAMA_TRADE_PARAMS_HOST = "http://gpu0:11434"
    agent._OLLAMA_TRADE_PARAMS_MODEL = "phi4-mini:latest"
    agent._OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL = "gemma3:1b"
    agent._OLLAMA_TRADE_PARAMS_FALLBACK_MODEL = "gemma3:1b"

    primary_host, primary_model, fallback_host, fallback_model = agent._get_trade_controls_ollama_targets()

    assert primary_host.endswith(":11435")
    assert primary_model == "gemma3:1b"
    assert fallback_host == ""
    assert fallback_model == ""


def test_trade_controls_targets_allow_cross_model_fallback_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TRADE_PARAMS_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TRADE_PARAMS_FALLBACK_HOST", raising=False)
    monkeypatch.setenv("OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", "true")
    agent = _agent("aggressive")
    agent._OLLAMA_TRADE_PARAMS_HOST = "http://gpu0:11434"
    agent._OLLAMA_TRADE_PARAMS_MODEL = "phi4-mini:latest"
    agent._OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL = "gemma3:1b"
    agent._OLLAMA_TRADE_PARAMS_FALLBACK_MODEL = "gemma3:1b"

    primary_host, primary_model, fallback_host, fallback_model = agent._get_trade_controls_ollama_targets()

    assert primary_host.endswith(":11435")
    assert primary_model == "gemma3:1b"
    assert fallback_host.endswith(":11434")
    assert fallback_model == "phi4-mini:latest"


def test_request_ollama_structured_retries_with_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _router_agent("aggressive")
    calls: list[tuple] = []
    responses = iter([
        "{bad json",
        '{"entry_low":100.0,"entry_high":100.1,"ttl_seconds":45}',
    ])

    def fake_do_generate(host, model, prompt, options, timeout, use_chat):
        calls.append((host, model, timeout))
        return next(responses)

    monkeypatch.setattr(agent._llm, "_do_generate", fake_do_generate)

    parsed, raw, meta = agent._request_ollama_structured(
        label="trade window",
        prompt="unit test",
        primary_host="http://gpu0:11434",
        primary_model="phi4-mini:latest",
        fallback_host="http://gpu1:11435",
        fallback_model="gemma3:1b",
        primary_timeout_sec=45,
        fallback_timeout_sec=30,
        options={"temperature": 0.0},
        parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
    )

    assert parsed["entry_high"] == pytest.approx(100.1)
    assert raw.startswith('{"entry_low"')
    assert meta["model"] == "gemma3:1b"
    assert meta["host"] == "http://gpu1:11435"
    assert meta["fallback_used"] is True


def test_request_ollama_structured_retries_same_target_before_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _router_agent("aggressive")
    calls: list[tuple] = []
    responses = iter([
        "{bad json",
        '{"entry_low":100.0,"entry_high":100.1,"ttl_seconds":45}',
    ])

    def fake_do_generate(host, model, prompt, options, timeout, use_chat):
        calls.append((host, model, timeout))
        return next(responses)

    monkeypatch.setattr(agent._llm, "_do_generate", fake_do_generate)

    parsed, raw, meta = agent._request_ollama_structured(
        label="trade window",
        prompt="unit test",
        primary_host="http://gpu1:11435",
        primary_model="gemma3:1b",
        fallback_host="http://gpu0:11434",
        fallback_model="phi4-mini:latest",
        primary_timeout_sec=45,
        fallback_timeout_sec=30,
        options={"temperature": 0.0},
        parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
        retries_per_target=2,
    )

    # Segunda tentativa AINDA no primary (retries_per_target=2) — não usou fallback.
    assert parsed["entry_high"] == pytest.approx(100.1)
    assert raw.startswith('{"entry_low"')
    assert meta["model"] == "gemma3:1b"
    assert meta["host"] == "http://gpu1:11435"
    assert meta["fallback_used"] is False
    assert meta["attempt"] == 2
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0] == "http://gpu1:11435"


def test_request_ollama_structured_repairs_primary_payload_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _router_agent("aggressive")
    calls: list[tuple] = []

    def fake_do_generate(host, model, prompt, options, timeout, use_chat):
        calls.append((host, model, timeout))
        # Payload truncado: o parser (_extract_json_object) deve reparar sem fallback.
        return '{"entry_low":100.0,"entry_high":100.1,"ttl_seconds":45,'

    monkeypatch.setattr(agent._llm, "_do_generate", fake_do_generate)

    parsed, raw, meta = agent._request_ollama_structured(
        label="trade window",
        prompt="unit test",
        primary_host="http://gpu0:11434",
        primary_model="phi4-mini:latest",
        fallback_host="http://gpu1:11435",
        fallback_model="gemma3:1b",
        primary_timeout_sec=45,
        fallback_timeout_sec=30,
        options={"temperature": 0.0},
        parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
    )

    assert parsed["entry_high"] == pytest.approx(100.1)
    assert raw.startswith('{"entry_low"')
    assert meta["model"] == "phi4-mini:latest"
    assert meta["host"] == "http://gpu0:11434"
    assert meta["fallback_used"] is False
    assert len(calls) == 1


def test_request_ollama_structured_503_falls_back_to_gpu1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Erro no primary (GPU0) deve cair para o fallback (GPU1), sem propagar exceção."""
    agent = _router_agent("aggressive")
    calls: list[tuple] = []

    def fake_do_generate(host, model, prompt, options, timeout, use_chat):
        calls.append((host, model))
        if "11434" in host:
            # GPU0 sobrecarregado — o LLMRouter propaga a exceção e tenta o próximo alvo.
            raise RuntimeError("HTTP 503 Service Unavailable")
        return '{"entry_low":100.0,"entry_high":100.1,"ttl_seconds":45}'

    monkeypatch.setattr(agent._llm, "_do_generate", fake_do_generate)

    parsed, raw, meta = agent._request_ollama_structured(
        label="trade window",
        prompt="unit test",
        primary_host="http://gpu0:11434",
        primary_model="phi4-mini:latest",
        fallback_host="http://gpu1:11435",
        fallback_model="phi4-mini:latest",
        primary_timeout_sec=45,
        fallback_timeout_sec=30,
        options={"temperature": 0.0},
        parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
    )

    assert parsed["entry_high"] == pytest.approx(100.1)
    assert meta["host"] == "http://gpu1:11435"
    assert meta["fallback_used"] is True
    # Primeira chamada foi GPU0 (falhou), segunda GPU1 (ok)
    assert "11434" in calls[0][0]
    assert "11435" in calls[1][0]


def test_request_ollama_structured_503_both_gpus_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quando GPU0 e GPU1 falham com 503, deve levantar RuntimeError com histórico."""
    agent = _router_agent("aggressive")

    def fake_do_generate(host, model, prompt, options, timeout, use_chat):
        raise RuntimeError("HTTP 503 Service Unavailable")

    monkeypatch.setattr(agent._llm, "_do_generate", fake_do_generate)

    with pytest.raises(RuntimeError, match="503"):
        agent._request_ollama_structured(
            label="trade window",
            prompt="unit test",
            primary_host="http://gpu0:11434",
            primary_model="phi4-mini:latest",
            fallback_host="http://gpu1:11435",
            fallback_model="phi4-mini:latest",
            primary_timeout_sec=10,
            fallback_timeout_sec=10,
            options={},
            parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
        )


# ── Gating do log de LLM pela config de runtime (painel) ──────────────────────

_DEF_CFG = {
    "enabled": True, "log_controls": True, "log_window": True, "log_plan": True,
    "sample_rate": 1.0, "max_prompt_chars": 0,
}


class _FakeLogDB:
    def __init__(self, cfg=None, raise_get=False):
        self._cfg = cfg if cfg is not None else dict(_DEF_CFG)
        self._raise_get = raise_get
        self.calls = []

    def get_llm_log_config(self):
        if self._raise_get:
            raise RuntimeError("db down")
        return self._cfg

    def record_llm_call(self, **kwargs):
        self.calls.append(kwargs)


def _logging_agent(cfg=None, raise_get=False):
    agent = _agent("aggressive")
    agent._current_profile = lambda: "aggressive"
    agent.db = _FakeLogDB(cfg, raise_get)
    return agent


def test_llm_log_gating_disabled_skips_record():
    agent = _logging_agent({**_DEF_CFG, "enabled": False})
    agent._record_llm_call(call_type="controls", prompt="p")
    assert agent.db.calls == []


def test_llm_log_gating_per_type_toggle():
    agent = _logging_agent({**_DEF_CFG, "log_controls": False})
    agent._record_llm_call(call_type="controls", prompt="p")   # desligado
    agent._record_llm_call(call_type="window", prompt="q")     # ligado
    assert len(agent.db.calls) == 1
    assert agent.db.calls[0]["call_type"] == "window"


def test_llm_log_gating_sample_rate(monkeypatch):
    monkeypatch.setattr(trading_agent.random, "random", lambda: 0.9)
    agent = _logging_agent({**_DEF_CFG, "sample_rate": 0.5})
    agent._record_llm_call(call_type="plan", prompt="p")  # 0.9 > 0.5 → pula
    assert agent.db.calls == []

    monkeypatch.setattr(trading_agent.random, "random", lambda: 0.1)
    agent2 = _logging_agent({**_DEF_CFG, "sample_rate": 0.5})
    agent2._record_llm_call(call_type="plan", prompt="p")  # 0.1 <= 0.5 → grava
    assert len(agent2.db.calls) == 1


def test_llm_log_gating_truncates_prompt():
    agent = _logging_agent({**_DEF_CFG, "max_prompt_chars": 5})
    agent._record_llm_call(call_type="plan", prompt="0123456789")
    assert agent.db.calls[0]["prompt"] == "01234"


def test_llm_log_gating_defaults_when_config_read_fails():
    # get_llm_log_config lança → cai nos defaults (enabled) → grava mesmo assim.
    agent = _logging_agent(raise_get=True)
    agent._record_llm_call(call_type="controls", prompt="p")
    assert len(agent.db.calls) == 1
