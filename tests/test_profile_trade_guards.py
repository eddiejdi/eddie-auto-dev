#!/usr/bin/env python3
"""Regressões para guards financeiros por profile."""

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


def _agent(profile: str = "aggressive", regime: str = "RANGING") -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.state = SimpleNamespace(
        profile=profile,
        position=0.001,
        entry_price=70000.0,
        dry_run=True,
    )
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(suggested_regime=regime)
    )
    agent._load_live_config = lambda: {
        "profile": profile,
        "max_daily_loss": 999999,
        "guardrails_active": False,
        "guardrails_positive_only_sells": False,
        "min_net_profit": {"usd": 0.01, "pct": 0.0005},
        "stop_loss_pct": 0.02,
    }
    return agent


def test_profile_min_net_profit_cfg_is_profiled() -> None:
    aggressive = _agent("aggressive")
    conservative = _agent("conservative")

    assert aggressive._get_profile_min_net_profit_cfg() == {"usd": 0.008, "pct": 0.0004}
    assert conservative._get_profile_min_net_profit_cfg() == {"usd": 0.012, "pct": 0.0006}


def test_sell_blocks_low_net_profit_in_ranging_profile() -> None:
    agent = _agent("aggressive", regime="RANGING")
    signal = SimpleNamespace(
        action="SELL",
        price=70050.0,
        confidence=0.72,
        reason="[BULLISH], ask pressure, news:bullish(cached)",
    )

    assert agent._calculate_trade_size(signal, signal.price) == 0


def test_sell_allows_low_net_profit_when_bearish_override_is_active() -> None:
    agent = _agent("conservative", regime="BEARISH")
    signal = SimpleNamespace(
        action="SELL",
        price=70050.0,
        confidence=0.72,
        reason="[BEARISH], bearish regime (67%), ask pressure, selling pressure",
    )

    assert agent._calculate_trade_size(signal, signal.price) == agent.state.position


def test_sell_allows_low_net_profit_when_price_hits_stop_loss_zone() -> None:
    agent = _agent("aggressive", regime="RANGING")
    signal = SimpleNamespace(
        action="SELL",
        price=68600.0,
        confidence=0.40,
        reason="RSI low, selling pressure",
    )

    assert agent._calculate_trade_size(signal, signal.price) == agent.state.position


def test_guardrails_positive_only_sells_block_negative_even_in_bearish_override() -> None:
    agent = _agent("conservative", regime="BEARISH")
    agent._load_live_config = lambda: {
        "profile": "conservative",
        "max_daily_loss": 0.085,
        "guardrails_active": True,
        "guardrails_positive_only_sells": True,
        "guardrails_min_sell_pnl_pct": 0.025,
        "min_net_profit": {"usd": 0.01, "pct": 0.0005},
        "stop_loss_pct": 0.02,
    }
    signal = SimpleNamespace(
        action="SELL",
        price=70050.0,
        confidence=0.72,
        reason="[BEARISH], bearish regime (67%), ask pressure, selling pressure",
    )

    assert agent._calculate_trade_size(signal, signal.price) == 0


def test_guardrails_positive_only_sells_block_small_positive_sell_below_25_pct() -> None:
    agent = _agent("conservative", regime="RANGING")
    agent._load_live_config = lambda: {
        "profile": "conservative",
        "max_daily_loss": 0.085,
        "guardrails_active": True,
        "guardrails_positive_only_sells": True,
        "guardrails_min_sell_pnl_pct": 0.025,
        "min_net_profit": {"usd": 0.01, "pct": 0.0005},
        "stop_loss_pct": 0.02,
    }
    signal = SimpleNamespace(
        action="SELL",
        price=70180.0,
        confidence=0.55,
        reason="[RANGING], mixed tape",
    )

    assert agent._calculate_trade_size(signal, signal.price) == 0


def test_guardrails_positive_only_sells_preserve_sell_above_25_pct() -> None:
    agent = _agent("conservative", regime="RANGING")
    agent._load_live_config = lambda: {
        "profile": "conservative",
        "max_daily_loss": 0.085,
        "guardrails_active": True,
        "guardrails_positive_only_sells": True,
        "guardrails_min_sell_pnl_pct": 0.025,
        "min_net_profit": {"usd": 0.01, "pct": 0.0005},
        "stop_loss_pct": 0.02,
    }
    signal = SimpleNamespace(
        action="SELL",
        price=71950.0,
        confidence=0.55,
        reason="[RANGING], mixed tape",
    )

    assert agent._calculate_trade_size(signal, signal.price) == agent.state.position
