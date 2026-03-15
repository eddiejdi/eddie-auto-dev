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


def _agent(profile: str = "aggressive") -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
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


def test_trade_window_host_routing_splits_profiles_between_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TRADE_WINDOW_FALLBACK_HOST", raising=False)
    agent = _agent("conservative")

    primary, fallback = agent._get_trade_window_ollama_hosts()

    assert primary.endswith(":11435")
    assert fallback.endswith(":11434")


def test_request_ollama_structured_retries_with_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent("aggressive")
    calls = []

    class FakeResponse:
        def __init__(self, status_code: int, response: str) -> None:
            self.status_code = status_code
            self._response = response

        def json(self) -> dict:
            return {"response": self._response}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, json: dict) -> FakeResponse:
            calls.append((url, json["model"], self.timeout))
            if len(calls) == 1:
                return FakeResponse(200, "{bad json")
            return FakeResponse(200, '{"entry_low":100.0,"entry_high":100.1,"ttl_seconds":45}')

    monkeypatch.setattr(trading_agent, "httpx", SimpleNamespace(Client=FakeClient))

    parsed, raw, meta = agent._request_ollama_structured(
        label="trade window",
        prompt="unit test",
        primary_host="http://gpu0:11434",
        primary_model="phi4-mini:latest",
        fallback_host="http://gpu1:11435",
        fallback_model="qwen3:0.6b",
        primary_timeout_sec=45,
        fallback_timeout_sec=30,
        options={"temperature": 0.0},
        parser=lambda payload: BitcoinTradingAgent._extract_json_object(payload),
    )

    assert parsed["entry_high"] == pytest.approx(100.1)
    assert raw.startswith('{"entry_low"')
    assert meta["model"] == "qwen3:0.6b"
    assert meta["host"] == "http://gpu1:11435"
    assert meta["fallback_used"] is True
    assert len(calls) == 2
