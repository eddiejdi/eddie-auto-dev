#!/usr/bin/env python3
"""Integração do track record confidence no trading_agent."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace())
import unittest.mock as _mock

_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)
_psycopg2_mock = types.ModuleType("psycopg2")
_psycopg2_extras = types.ModuleType("psycopg2.extras")
_psycopg2_pool = types.ModuleType("psycopg2.pool")
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", _psycopg2_extras)
sys.modules.setdefault("psycopg2.pool", _psycopg2_pool)
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

from fast_model import Signal
from trading_agent import BitcoinTradingAgent


def _agent_with_sells(sells) -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(profile="conservative", dry_run=False)
    agent._load_live_config = lambda: {
        "profile": "conservative",
        "track_record_confidence": {
            "enabled": True,
            "mode": "apply",
            "lookback_hours": 72,
            "min_sell_samples": 5,
            "max_boost": 0.10,
            "max_penalty": 0.08,
            "pnl_scale_usd": 2.0,
        },
    }
    agent._current_profile = lambda: "conservative"
    agent.db = SimpleNamespace(
        get_profile_realized_sells=lambda **kwargs: sells,
    )
    from track_record_confidence import TrackRecordConfidence

    agent._track_record = TrackRecordConfidence(agent.db)
    agent._last_track_record_snapshot = None
    return agent


def test_apply_track_record_boosts_buy_confidence() -> None:
    sells = [{"side": "sell", "pnl": 0.02, "pnl_pct": 2.0}] * 6
    agent = _agent_with_sells(sells)
    signal = Signal(action="BUY", confidence=0.58, price=100.0, reason="test")
    adjusted = agent._apply_track_record_confidence(signal)
    assert adjusted.confidence > 0.58
    assert adjusted.features["raw_confidence"] == 0.58
    assert adjusted.features["track_record_boost"] > 0


def test_apply_track_record_boosts_sell_confidence() -> None:
    sells = [{"side": "sell", "pnl": 0.02, "pnl_pct": 2.0}] * 6
    agent = _agent_with_sells(sells)
    signal = Signal(action="SELL", confidence=0.55, price=100.0, reason="test")
    adjusted = agent._apply_track_record_confidence(signal)
    assert adjusted.confidence > 0.55


def test_hold_signal_is_not_adjusted() -> None:
    agent = _agent_with_sells([])
    signal = Signal(action="HOLD", confidence=0.40, price=100.0, reason="test")
    adjusted = agent._apply_track_record_confidence(signal)
    assert adjusted.confidence == 0.40
    assert "raw_confidence" not in (adjusted.features or {})