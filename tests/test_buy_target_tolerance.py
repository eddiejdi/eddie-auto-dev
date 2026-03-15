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

from trading_agent import BitcoinTradingAgent


def _agent() -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.state = SimpleNamespace(profile="aggressive")
    agent._load_live_config = lambda: {"profile": agent.state.profile}
    return agent


def _rag(*, regime: str = "RANGING") -> SimpleNamespace:
    return SimpleNamespace(
        suggested_regime=regime,
        regime_confidence=0.7,
        ai_buy_target_price=100.0,
        ai_buy_target_reason="unit-test",
    )


def _signal(reason: str) -> SimpleNamespace:
    return SimpleNamespace(action="BUY", reason=reason, price=100.0, confidence=0.65)


def test_aggressive_tolerance_requires_clean_bullish_context() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("RSI low, bid pressure, buying pressure, news:bullish(cached)")

    tolerance = agent._get_buy_target_tolerance_pct(rag, signal)

    assert tolerance == 0.0008


def test_buy_target_tolerance_is_zero_in_strong_bearish_context() -> None:
    agent = _agent()
    rag = _rag(regime="BEARISH")
    signal = _signal("[BEARISH], bearish regime (67%), ask pressure, selling pressure")

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0


def test_aggressive_tolerance_is_zero_without_news_bullish() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("RSI oversold, bid pressure, buying pressure")

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0


def test_conservative_tolerance_requires_high_confidence_oversold_reversal() -> None:
    agent = _agent()
    agent.state.profile = "conservative"
    rag = _rag(regime="RANGING")
    signal = SimpleNamespace(action="BUY", reason="RSI oversold, bid pressure, news:bullish(cached)", price=100.0, confidence=0.67)

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0008


def test_conservative_tolerance_is_zero_below_confidence_gate() -> None:
    agent = _agent()
    agent.state.profile = "conservative"
    rag = _rag(regime="RANGING")
    signal = SimpleNamespace(action="BUY", reason="RSI oversold, bid pressure, news:bullish(cached)", price=100.0, confidence=0.64)

    assert agent._get_buy_target_tolerance_pct(rag, signal) == 0.0


def test_aggressive_uplift_requires_strong_bullish_context() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("RSI oversold, bid pressure, buying pressure, news:bullish(cached)")

    uplift = agent._get_buy_target_uplift_pct(rag, signal)

    assert uplift == 0.0008


def test_conservative_uplift_is_smaller_and_needs_clean_oversold_signal() -> None:
    agent = _agent()
    agent.state.profile = "conservative"
    rag = _rag(regime="RANGING")
    signal = SimpleNamespace(
        action="BUY",
        reason="RSI oversold, bid pressure, news:bullish(cached)",
        price=100.0,
        confidence=0.67,
    )

    assert agent._get_buy_target_uplift_pct(rag, signal) == 0.0002


def test_uplift_is_zero_in_conflicting_context() -> None:
    agent = _agent()
    rag = _rag(regime="RANGING")
    signal = _signal("RSI oversold, bid pressure, buying pressure, ask pressure, news:bullish(cached)")

    assert agent._get_buy_target_uplift_pct(rag, signal) == 0.0
