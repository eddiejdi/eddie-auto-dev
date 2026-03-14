#!/usr/bin/env python3
"""Regressões para a tolerância do buy target no trading agent."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types

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
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(
        TrainingDatabase=object,
        TrainingManager=object,
    ),
)
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))

from trading_agent import BitcoinTradingAgent


def _agent() -> BitcoinTradingAgent:
    return BitcoinTradingAgent.__new__(BitcoinTradingAgent)


def _rag(*, regime: str = "RANGING") -> SimpleNamespace:
    return SimpleNamespace(
        suggested_regime=regime,
        regime_confidence=0.7,
        ai_buy_target_price=100.0,
        ai_buy_target_reason="unit-test",
    )


def _signal(reason: str) -> SimpleNamespace:
    return SimpleNamespace(action="BUY", reason=reason, price=100.0, confidence=0.65)


def test_buy_target_tolerance_relaxes_ranging_entries() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("RSI oversold, bid pressure, buying pressure")

    tolerance = agent._get_buy_target_tolerance_pct(rag, signal)

    assert tolerance >= 0.0008
    assert tolerance <= 0.0014


def test_buy_target_tolerance_is_zero_in_strong_bearish_context() -> None:
    agent = _agent()
    rag = _rag(regime="BEARISH")
    signal = _signal("[BEARISH], bearish regime (67%), ask pressure, selling pressure")

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0


def test_buy_target_tolerance_stays_tight_when_context_conflicts() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("[BULLISH], ask pressure, selling pressure, buying pressure")

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0003
