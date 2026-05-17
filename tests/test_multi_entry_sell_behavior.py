#!/usr/bin/env python3
"""Testes para SELL com múltiplas entradas no BTC agent."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
        _resolve_telegram_bot_token=lambda: "",
        _resolve_telegram_chat_id=lambda: "",
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(FastTradingModel=object, MarketState=object, Signal=object),
)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(TrainingDatabase=object, TrainingManager=object),
)
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))

from trading_agent import BitcoinTradingAgent


def _make_agent(entries: list[dict], *, dry_run: bool = True) -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    total_position = sum(float(entry["size"]) for entry in entries)
    weighted_cost = sum(float(entry["size"]) * float(entry["price"]) for entry in entries)

    agent.symbol = "BTC-USDT"
    agent._trade_lock = threading.Lock()
    agent._on_trade_callbacks = []
    agent._last_trade_id = 0
    agent.db = MagicMock()
    agent.db.record_trade.return_value = 101
    agent.db.update_trade_pnl.return_value = None
    agent._current_profile = lambda: "aggressive"
    agent._get_guardrail_sell_verdict = lambda price: None
    agent.state = SimpleNamespace(
        position=total_position,
        entry_price=weighted_cost / total_position if total_position else 0.0,
        entries=[dict(entry) for entry in entries],
        dry_run=dry_run,
        total_pnl=0.0,
        winning_trades=0,
        total_trades=0,
        daily_trades=0,
        last_trade_time=0.0,
        trailing_high=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        position_count=len(entries),
        raw_entry_count=len(entries),
        logical_position_slots=len(entries),
        last_sell_entry_price=0.0,
        buy_success_pressure=0.0,
        buy_success_factor=1.0,
        buy_dynamic_batch_cap_usdt=0.0,
        dca_valley_low=0.0,
    )
    return agent


def test_normal_sell_with_multi_entry_realizes_only_profitable_slots() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0},
        ]
    )
    signal = SimpleNamespace(
        action="SELL",
        confidence=0.80,
        reason="MODEL_EXIT",
        price=92_000.0,
        features={},
    )

    result = agent._execute_trade(signal, 92_000.0, force=False)

    assert result is True
    assert agent.state.position == pytest.approx(0.001)
    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["price"] == pytest.approx(100_000.0)
    assert agent.db.record_trade.call_count == 1


def test_forced_sell_with_multi_entry_still_liquidates_all() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0},
        ]
    )
    agent._get_guardrail_sell_verdict = lambda price: None
    signal = SimpleNamespace(
        action="SELL",
        confidence=1.0,
        reason="AUTO_STOP_LOSS",
        price=92_000.0,
        features={},
    )

    result = agent._execute_trade(signal, 92_000.0, force=True)

    assert result is True
    assert agent.state.position == 0.0
    assert agent.state.entries == []
    assert agent.db.record_trade.call_count == 1
